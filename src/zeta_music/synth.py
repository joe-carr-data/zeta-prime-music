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


def _ks_loop(freq: float, sr: int, t60: float) -> tuple[int, float, float]:
    """Loop parameters (integer delay P, fraction f, raw gain g) at sample rate ``sr``.

    Per-period decay so the fundamental falls 60 dB in t60 seconds. The loop filter also
    attenuates the fundamental by |H(w0)| every period, so that is divided out; ``g`` may come
    out >= 1 for high notes, in which case the caller oversamples.
    """
    period = sr / freq
    p = max(int(np.floor(period - 0.5)), 2)
    f = float(np.clip(period - p - 0.5, 0.0, 1.0))
    w0 = 2.0 * np.pi * freq / sr
    h_w0 = abs(0.5 * (1.0 - f) + 0.5 * np.exp(-1j * w0) + 0.5 * f * np.exp(-2j * w0))
    return p, f, 10.0 ** (-3.0 / (t60 * freq)) / max(h_w0, 1e-6)


MAX_LOOP_GAIN = 0.9999  # |H| <= 1 with equality at DC, so g < 1 keeps every frequency stable


def oversampling_factor(freq: float, sr: int, t60: float) -> int:
    """Smallest of 1/2/4/8 at which the loop can hold ``t60`` for ANY fractional delay.

    Uses the worst case f = 0.5 (|H| = cos^2(w/2), the strongest loss), so the factor rises
    monotonically with pitch instead of flickering between neighbouring notes.
    """
    over = 1
    while over < 8:
        w0 = 2.0 * np.pi * freq / (sr * over)
        if 10.0 ** (-3.0 / (t60 * freq)) / np.cos(w0 / 2) ** 2 <= MAX_LOOP_GAIN:
            break
        over *= 2
    return over


def pluck(
    freq: float,
    dur: float,
    sr: int,
    rng: np.random.Generator,
    brightness: float = 0.6,
    t60: float = 2.5,
) -> Audio:
    """Karplus–Strong plucked string with fractional-delay tuning and calibrated decay.

    Loop filter ``h = [(1-f)/2, 1/2, f/2]`` is always a lowpass and has phase delay
    ``0.5 + f`` at low frequencies, so the total loop delay ``P + 0.5 + f`` equals the period
    exactly. The recursion only reaches ``P`` samples back, so it is evaluated a period at a
    time (vectorised).

    High notes lose more to the loop filter per period than a stable gain can restore, so they
    are synthesised at 2x/4x/8x the sample rate (the per-period loss falls ~ with the square of
    the factor) and decimated. Notes that do not need it are bit-identical to plain KS.

    Trade-off (measured, documented): with a 3-tap loop filter the harmonics' decay relative to
    the fundamental is fixed by the filter shape, so holding t60 at high pitch necessarily damps
    upper harmonics less: attack/sustain spectral centroid rises ~1.4-1.7x across each factor
    boundary (778, 1227, 1929 Hz at 44.1 kHz, t60 2.8 s). The factor is monotonic in pitch (no
    flicker) and the excitation filter is fixed in output-rate Hz, so only the loop contributes.
    """
    from math import gcd

    n = int(dur * sr)
    over = oversampling_factor(freq, sr, t60)
    p, f, g = _ks_loop(freq, sr * over, t60)
    g = min(g, MAX_LOOP_GAIN)
    sr_int = sr * over
    n_int = n * over
    excitation = rng.uniform(-1.0, 1.0, p + 2)
    # brighten/darken the initial burst with a one-pole lowpass whose cutoff is fixed in Hz at
    # the OUTPUT rate (pole^(1/over) at the internal rate), so oversampling does not brighten it
    pole = ((1.0 - brightness) * 0.9) ** (1.0 / over)
    excitation = signal.lfilter([1.0 - pole], [1.0, -pole], excitation)
    excitation -= excitation.mean()
    y = np.zeros(n_int + p + 2)
    y[: p + 2] = excitation
    h0, h1, h2 = g * 0.5 * (1.0 - f), g * 0.5, g * 0.5 * f
    i = p + 2
    while i < y.size:
        j = min(i + p, y.size)
        y[i:j] = h0 * y[i - p : j - p] + h1 * y[i - p - 1 : j - p - 1] + h2 * y[i - p - 2 : j - p - 2]
        i = j
    out = y[p + 2 : p + 2 + n_int]
    if over > 1:
        k = gcd(sr_int, sr)
        out = signal.resample_poly(out, sr // k, sr_int // k)[:n]
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
    energy = np.sqrt(np.sum(ir**2, axis=0, keepdims=True))
    if not np.all(energy > 0):  # degenerate room (t60 shorter than a sample after predelay): dry only
        return np.array(stereo, dtype=np.float64, copy=True)
    ir /= energy
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
