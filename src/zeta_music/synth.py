"""Small, dependency-light DSP toolkit: oscillators, plucked strings, bells, reverb, mastering.

All functions are pure (no global state); randomness is injected via ``numpy.random.Generator``.
Audio buffers are float64, mono shape ``(n,)`` or stereo shape ``(n, 2)``.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy import signal

__all__ = [
    "add_at",
    "bell",
    "db_to_amp",
    "exp_decay",
    "master",
    "pan_equal_power",
    "pluck",
    "reverb",
    "smooth",
]

Audio = NDArray[np.float64]


def db_to_amp(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def exp_decay(n: int, sr: int, t60: float, attack: float = 0.002) -> Audio:
    """Envelope with a short linear attack and exponential decay reaching -60 dB at ``t60``."""
    t = np.arange(n) / sr
    env = np.exp(-6.907755 * t / max(t60, 1e-4))
    na = min(n, max(1, int(attack * sr)))
    env[:na] *= np.linspace(0.0, 1.0, na, endpoint=False)
    return env


def smooth(x: Audio, sr: float, cutoff_hz: float) -> Audio:
    """Zero-phase one-pole-ish lowpass (2nd-order Butterworth, filtfilt)."""
    if x.size < 16:
        return x.copy()
    b, a = signal.butter(2, min(cutoff_hz / (sr / 2), 0.99))
    return signal.filtfilt(b, a, x)


def pluck(
    freq: float,
    dur: float,
    sr: int,
    rng: np.random.Generator,
    brightness: float = 0.6,
    t60: float = 2.5,
) -> Audio:
    """Karplus–Strong plucked string with fractional-delay tuning and decay control.

    Loop filter ``h = [(1-f)/2, 1/2, f/2]`` is always a lowpass and has phase delay
    ``0.5 + f`` at low frequencies, so the total loop delay ``P + 0.5 + f`` equals the period
    exactly. The recursion only reaches ``P`` samples back, so it is evaluated a period at a
    time (vectorised).
    """
    n = int(dur * sr)
    period = sr / freq
    p = max(int(np.floor(period - 0.5)), 2)
    f = float(np.clip(period - p - 0.5, 0.0, 1.0))
    # loop gain so the fundamental decays 60 dB in t60 seconds
    g = 10.0 ** (-3.0 / (t60 * freq))
    excitation = rng.uniform(-1.0, 1.0, p + 2)
    # brighten/darken the initial burst with a one-pole lowpass
    pole = (1.0 - brightness) * 0.9
    excitation = signal.lfilter([1.0 - pole], [1.0, -pole], excitation)
    excitation -= excitation.mean()
    y = np.zeros(n + p + 2)
    y[: p + 2] = excitation
    h0, h1, h2 = g * 0.5 * (1.0 - f), g * 0.5, g * 0.5 * f
    i = p + 2
    while i < y.size:
        j = min(i + p, y.size)
        y[i:j] = h0 * y[i - p : j - p] + h1 * y[i - p - 1 : j - p - 1] + h2 * y[i - p - 2 : j - p - 2]
        i = j
    out = y[p + 2 : p + 2 + n]
    fade = min(n, int(0.01 * sr))
    if fade:
        out[-fade:] *= np.linspace(1.0, 0.0, fade)
    return out


def bell(freq: float, dur: float, sr: int, t60: float = 3.0, index: float = 2.2) -> Audio:
    """Two-operator FM bell (inharmonic 1:1.4 ratio), index decays with the envelope."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    env = exp_decay(n, sr, t60, attack=0.003)
    mod = index * env * np.sin(2 * np.pi * freq * 1.4 * t)
    return env * np.sin(2 * np.pi * freq * t + mod)


def pan_equal_power(mono: Audio, pan: float) -> Audio:
    """Pan in [-1, 1] with constant power."""
    theta = (np.clip(pan, -1.0, 1.0) + 1.0) * np.pi / 4.0
    return np.stack([mono * np.cos(theta), mono * np.sin(theta)], axis=1)


def add_at(buf: Audio, clip: Audio, start: int) -> None:
    """Mix ``clip`` into ``buf`` starting at sample ``start`` (clipped to buffer bounds)."""
    if start >= buf.shape[0] or start + clip.shape[0] <= 0:
        return
    s0 = max(start, 0)
    s1 = min(start + clip.shape[0], buf.shape[0])
    buf[s0:s1] += clip[s0 - start : s1 - start]


def reverb(
    stereo: Audio,
    sr: int,
    rng: np.random.Generator,
    t60: float = 3.2,
    predelay: float = 0.025,
    damping_hz: float = 6000.0,
    mix: float = 0.25,
) -> Audio:
    """Convolution reverb with a synthetic, decorrelated stereo IR (exp-decaying filtered noise)."""
    n_ir = int((t60 + predelay) * sr)
    t = np.arange(n_ir) / sr
    env = np.exp(-6.907755 * t / t60)
    env[: int(predelay * sr)] = 0.0
    b, a = signal.butter(1, min(damping_hz, 0.45 * sr) / (sr / 2))
    ir = np.stack([signal.lfilter(b, a, rng.standard_normal(n_ir)) * env for _ in range(2)], axis=1)
    ir /= np.sqrt(np.sum(ir**2, axis=0, keepdims=True))
    out = np.array(stereo, dtype=np.float64, copy=True)
    for c in range(2):  # one channel at a time, blended in place: no full-length stereo temporaries
        wet = signal.fftconvolve(out[:, c], ir[:, c])[: out.shape[0]]
        out[:, c] *= 1.0 - mix
        out[:, c] += mix * wet
        del wet
    return out


def master(stereo: Audio, sr: int, peak_db: float = -1.0, drive: float = 1.2) -> Audio:
    """DC-block, gentle tanh saturation and peak normalisation to ``peak_db`` dBFS."""
    b, a = signal.butter(2, 20.0 / (sr / 2), btype="highpass")
    x = signal.filtfilt(b, a, stereo, axis=0)
    peak = float(np.max(np.abs(x))) or 1.0
    x = np.tanh(drive * x / peak) / np.tanh(drive)
    x *= db_to_amp(peak_db) / (float(np.max(np.abs(x))) or 1.0)
    return x
