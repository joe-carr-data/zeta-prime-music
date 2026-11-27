r"""The composition engine: turns the explicit formula into a piece of music.

Musical mapping (see ``docs/COMPOSITION.md`` for the full rationale)
--------------------------------------------------------------------
* **Timeline.** A control-rate clock drives a point ``x(τ)`` along the number line and a
  (fractional) count ``N(τ)`` of nontrivial zeros "switched on".
* **Drone – the zeros.** Zero ``k`` sounds as a sine partial at ``base·(γ_k/γ_1)``; its
  amplitude follows the explicit-formula weight ``1/|ρ_k|`` and is modulated by its own
  oscillation ``cos(γ_k ln x)`` at the current ``x``. Adding zeros literally adds partials.
* **Plucks – the primes.** The truncated spike density ``ψ'_N(x)`` is scanned as ``x`` moves.
  Every peak becomes a plucked note. Peak *height* is normalised to a *salience* that tends to
  ``Λ(n)/log n = 1/k`` at ``n = p^k``—so primes ring at full strength and prime powers appear as
  quieter bell "overtones" (as noted in the video). Pitch is the folded harmonic ``x/2^⌊log₂x⌋``
  of a fundamental, evaluated at the *measured* peak position: with few zeros the peaks are
  off-integer and the music is microtonal and out of tune; as zeros are added, the peaks lock
  onto the prime powers and the pitches snap into just intonation (3 → fifth, 5 → major third,
  7 → harmonic seventh …).
* **Breath** – band-limited noise shaped by the raw salience curve: the sum itself, audible.
* **Pole** – a low sine for the main term (the pole of ζ at s = 1 → the "1" in ψ'(x)).
"""

from __future__ import annotations

import itertools
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy import signal
from scipy.signal import find_peaks

from . import synth
from .config import CompositionConfig, Section
from .explicit import von_mangoldt
from .zeros import load_zeros

__all__ = ["Event", "RenderResult", "Timeline", "build_timeline", "detect_events", "render", "salience_curve"]

log = logging.getLogger(__name__)
FloatArray = NDArray[np.float64]
EventKind = Literal["prime", "prime_power", "ghost"]


# --------------------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Timeline:
    rate: int
    t: FloatArray  # seconds
    x: FloatArray  # point on the number line
    n_zeros: FloatArray  # fractional number of active zeros
    section: NDArray[np.int64]  # section index
    drone_gain: FloatArray
    pluck_gain: FloatArray
    breath_gain: FloatArray


def _section_curves(sec: Section, u: FloatArray) -> tuple[FloatArray, FloatArray]:
    """x(u) and N(u) for local time u in [0, duration)."""
    if sec.loop:
        phase = np.mod(u, sec.loop) / sec.loop
        segment = np.floor(u / sec.loop).astype(int)
        n_segments = int(np.ceil(sec.duration / sec.loop - 1e-9))
    else:
        phase = u / sec.duration
        n_segments = len(sec.zeros_steps) if sec.zeros_steps else 1
        segment = np.minimum((u / sec.duration * n_segments).astype(int), n_segments - 1)

    if sec.sweep == "exp":
        x = sec.x_start * (sec.x_end / sec.x_start) ** phase
    else:
        x = sec.x_start + (sec.x_end - sec.x_start) * phase

    if sec.zeros_steps:
        steps = np.asarray(sec.zeros_steps, dtype=float)
        n = steps[np.minimum(segment, steps.size - 1)]
    else:
        frac = u / sec.duration
        a, b = float(sec.zeros_start), float(sec.zeros_end)
        n = a * (b / a) ** frac if a > 0 and b > 0 else a + (b - a) * frac
    return x, n


def build_timeline(cfg: CompositionConfig) -> Timeline:
    rate = cfg.control_rate
    parts: dict[str, list[FloatArray]] = {k: [] for k in ("x", "n", "sec", "dg", "pg", "bg")}
    for i, sec in enumerate(cfg.sections):
        u = np.arange(round(sec.duration * rate)) / rate
        x, n = _section_curves(sec, u)
        parts["x"].append(x)
        parts["n"].append(n)
        parts["sec"].append(np.full(u.size, i))
        parts["dg"].append(np.full(u.size, sec.drone_gain))
        parts["pg"].append(np.full(u.size, sec.pluck_gain))
        parts["bg"].append(np.full(u.size, sec.breath_gain))
    cat = {k: np.concatenate(v) for k, v in parts.items()}
    t = np.arange(cat["x"].size) / rate
    return Timeline(
        rate=rate,
        t=t,
        x=cat["x"],
        n_zeros=cat["n"],
        section=cat["sec"].astype(np.int64),
        drone_gain=synth.smooth(cat["dg"], rate, 0.8),
        pluck_gain=synth.smooth(cat["pg"], rate, 2.0),
        breath_gain=synth.smooth(cat["bg"], rate, 0.8),
    )


# --------------------------------------------------------------------------------------
# Spike density with time-varying zero set
# --------------------------------------------------------------------------------------
def _zero_weights(k: FloatArray, n: FloatArray, taper: str) -> FloatArray:
    """Weights for zero index k (0-based, column) at fractional count n (row)."""
    presence = np.clip(n[None, :] - k[:, None], 0.0, 1.0)
    if taper == "none":
        return presence
    u = (k[:, None] + 0.5) / np.maximum(n[None, :], 1e-9)
    match taper:
        case "gauss":
            shape = np.exp(-0.5 * (2.5 * u) ** 2)
        case "hann":
            shape = 0.5 * (1 + np.cos(np.pi * np.clip(u, 0, 1)))
        case "fejer":
            shape = np.clip(1 - u, 0, 1)
        case _:
            raise ValueError(taper)
    return presence * shape


def salience_curve(
    x: FloatArray, n_zeros: FloatArray, gammas: FloatArray, taper: str = "gauss", chunk: int = 20000
) -> FloatArray:
    r"""Normalised prime-spike curve.

    ``S(x) = (ψ'_N(x) − 1) · x / log x · π / I_w`` where ``I_w = Σ_k w_k · 2π / log(γ_k / 2π)``
    approximates ``∫ w(γ) dγ``. By the Weil explicit formula the spike at ``n`` has height
    ``≈ Λ(n)/n · I_w / π``, so ``S(n) ≈ Λ(n)/log n`` (1 at primes, 1/k at ``p^k``).
    """
    g = np.asarray(gammas, dtype=np.float64)
    k = np.arange(g.size, dtype=np.float64)
    spacing = 2 * np.pi / np.log(g / (2 * np.pi))
    out = np.empty_like(x)
    for s in range(0, x.size, chunk):
        sl = slice(s, min(s + chunk, x.size))
        xc, nc = x[sl], n_zeros[sl]
        w = _zero_weights(k, nc, taper)
        osc = np.einsum("kj,kj->j", w, np.cos(np.outer(g, np.log(xc))))
        dens_minus_1 = -2.0 * xc**-0.5 * osc - 1.0 / (xc * (xc * xc - 1.0))
        i_w = np.maximum(spacing @ w, 1e-9)
        out[sl] = dens_minus_1 * xc / np.log(xc) * np.pi / i_w
    return out


# --------------------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Event:
    time: float
    x: float
    salience: float
    nearest: int
    kind: EventKind
    n_zeros: float
    freq: float
    pan: float

    @property
    def prime(self) -> int | None:
        if self.kind == "ghost":
            return None
        n, p = self.nearest, 2
        while n % p:
            p += 1
        return p


def fold(x: FloatArray | float) -> FloatArray:
    """Octave-reduce a harmonic number into [1, 2): the pitch class of harmonic x."""
    xa = np.asarray(x, dtype=np.float64)
    return xa / 2.0 ** np.floor(np.log2(xa))


def event_pitch(x: float, base_hz: float) -> float:
    """Pitch for a peak at ``x``: the folded harmonic of the nearest integer ``n``, detuned by ``x/n``.

    Register and pitch class come from the integer, so a peak converging on ``n`` from either side
    glides smoothly into tune instead of jumping an octave at powers of two.
    """
    n = max(round(x), 1)
    octave = min(3.0, float(np.floor(np.log2(n) / 2.5)))
    return float(base_hz * fold(float(n)) * 2.0**octave * (x / n))


def event_pan(x: float) -> float:
    n = max(round(x), 1)
    return float(np.clip((fold(float(n)) - 1.5) * 1.5, -0.85, 0.85))


def detect_events(tl: Timeline, sal: FloatArray, cfg: CompositionConfig) -> list[Event]:
    """Find peaks of the salience curve and classify them as primes, prime powers or ghosts."""
    # Peaks are found section-by-section and loop-by-loop so wrap-around never fuses peaks.
    breaks = np.flatnonzero(np.diff(tl.x) < 0) + 1
    bounds = [0, *breaks.tolist(), tl.x.size]
    events: list[Event] = []
    for a, b in itertools.pairwise(bounds):
        seg = sal[a:b]
        if seg.size < 3:
            continue
        idx, _props = find_peaks(seg, prominence=cfg.peak_prominence, height=cfg.peak_prominence)
        for i in idx:
            j = a + int(i)
            # parabolic interpolation for sub-sample peak position
            if 0 < i < seg.size - 1:
                y0, y1, y2 = seg[i - 1], seg[i], seg[i + 1]
                denom = y0 - 2 * y1 + y2
                d = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
            else:
                d = 0.0
            xj = float(np.interp(j + d, np.arange(tl.x.size), tl.x))
            tj = (j + d) / tl.rate
            nearest = round(xj)
            lam = von_mangoldt(nearest)
            # tolerance: half the kernel width in x (~ x * pi / gamma_eff), capped
            n_act = max(tl.n_zeros[j], 1.0)
            tol = min(0.25, 0.5 * xj * np.pi / (14.0 + 2.2 * n_act))
            kind: EventKind
            if lam > 0 and abs(xj - nearest) <= tol:
                kind = "prime" if abs(lam - np.log(nearest)) < 1e-9 else "prime_power"
            else:
                kind = "ghost"
            f = event_pitch(xj, cfg.pluck_base_hz)
            pan = event_pan(xj)
            events.append(Event(tj, xj, float(seg[i]), nearest, kind, float(tl.n_zeros[j]), f, pan))
    events.sort(key=lambda e: e.time)
    return events


# --------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------
@dataclass
class RenderResult:
    audio: FloatArray  # (n, 2)
    sample_rate: int
    events: list[Event]
    timeline: Timeline
    salience: FloatArray

    def stats(self) -> dict[str, int]:
        kinds = [e.kind for e in self.events]
        return {k: kinds.count(k) for k in ("prime", "prime_power", "ghost")}


def _upsample(ctrl: FloatArray, rate: int, n_audio: int, sr: int) -> FloatArray:
    ta = np.arange(n_audio, dtype=np.float64) / sr
    tc = np.arange(ctrl.size, dtype=np.float64) / rate
    return np.interp(ta, tc, ctrl)


def _render_drone(cfg: CompositionConfig, tl: Timeline, gammas: FloatArray, n_audio: int) -> FloatArray:
    sr = cfg.sample_rate
    out = np.zeros((n_audio, 2))
    t = np.arange(n_audio, dtype=np.float64) / sr
    rng = np.random.default_rng(cfg.seed + 1)
    log_x = np.log(tl.x)
    n_smooth = synth.smooth(tl.n_zeros, tl.rate, 1.5)
    amps_sq = np.zeros(tl.t.size)
    rows: list[tuple[float, FloatArray, float]] = []
    for k, g in enumerate(gammas):
        f = cfg.drone_base_hz * (g / gammas[0]) ** cfg.drone_exponent
        if f > cfg.drone_max_hz:
            break
        presence = np.clip(n_smooth - k, 0.0, 1.0)
        if not presence.any():
            continue
        weight = abs(1.0 / complex(0.5, g)) / abs(1.0 / complex(0.5, gammas[0]))
        trem = 1.0 - cfg.drone_tremolo + cfg.drone_tremolo * 0.5 * (1.0 + np.cos(g * log_x))
        trem = synth.smooth(trem, tl.rate, 120.0)
        amp = presence * weight * trem
        amps_sq += (presence * weight) ** 2
        rows.append((f, amp, float(rng.uniform(-0.7, 0.7))))
    # normalise so adding zeros thickens the chord without a loudness explosion
    norm = 1.0 / np.sqrt(np.maximum(amps_sq, 1.0))
    norm = synth.smooth(norm, tl.rate, 0.5) * tl.drone_gain
    for f, amp, pan in rows:
        phase0 = rng.uniform(0, 2 * np.pi)  # drawn unconditionally: keeps output seed-stable
        ctrl = amp * norm
        active = np.flatnonzero(ctrl > 1e-7)
        if active.size == 0:
            continue
        # synthesise only the span where this zero is switched on
        a = max(int((active[0] - 1) / tl.rate * sr), 0)
        b = min(int((active[-1] + 1) / tl.rate * sr) + 1, n_audio)
        ts = t[a:b]
        env = np.interp(ts, np.arange(ctrl.size) / tl.rate, ctrl)
        tone = env * np.sin(2 * np.pi * f * ts + phase0)
        theta = (pan + 1.0) * np.pi / 4.0
        out[a:b, 0] += tone * np.cos(theta)
        out[a:b, 1] += tone * np.sin(theta)
    return out


def _render_notes(
    cfg: CompositionConfig, tl: Timeline, events: list[Event], n_audio: int
) -> tuple[FloatArray, FloatArray]:
    sr = cfg.sample_rate
    rng = np.random.default_rng(cfg.seed + 2)
    plucks = np.zeros((n_audio, 2))
    bells = np.zeros((n_audio, 2))
    for e in events:
        j = min(int(e.time * tl.rate), tl.t.size - 1)
        gain = float(tl.pluck_gain[j]) * float(np.clip(e.salience, 0.0, 1.3))
        if gain <= 1e-4:
            continue
        start = int(e.time * sr)
        if e.kind == "prime":
            note = synth.pluck(e.freq, 3.0, sr, rng, brightness=0.65, t60=2.8)
            synth.add_at(plucks, synth.pan_equal_power(note * gain, e.pan), start)
        elif e.kind == "prime_power":
            note = synth.bell(e.freq * 2.0, 3.5, sr, t60=3.0)
            synth.add_at(bells, synth.pan_equal_power(note * gain, -e.pan), start)
        else:  # ghost: dull, short, quieter pluck at the (microtonal) peak pitch
            note = synth.pluck(e.freq, 1.2, sr, rng, brightness=0.25, t60=0.8)
            synth.add_at(plucks, synth.pan_equal_power(note * gain * 0.55, e.pan), start)
    return plucks, bells


def _render_breath(cfg: CompositionConfig, tl: Timeline, sal: FloatArray, n_audio: int) -> FloatArray:
    sr = cfg.sample_rate
    rng = np.random.default_rng(cfg.seed + 3)
    env = np.clip(sal, 0.0, 1.5) ** 2 * tl.breath_gain
    env = _upsample(synth.smooth(env, tl.rate, 60.0), tl.rate, n_audio, sr)
    sos = signal.butter(2, [250.0, 2500.0], btype="bandpass", fs=sr, output="sos")
    noise = signal.sosfilt(sos, rng.standard_normal((n_audio, 2)), axis=0)
    return noise * env[:, None]


def _render_pole(cfg: CompositionConfig, n_audio: int) -> FloatArray:
    sr = cfg.sample_rate
    t = np.arange(n_audio) / sr
    f = cfg.drone_base_hz / 2.0
    tone = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t + 0.3)
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * t / 23.0)
    return np.stack([tone * swell, tone * swell], axis=1)


def _fades(n: int, sr: int, fade_in: float = 3.0, fade_out: float = 8.0) -> FloatArray:
    env = np.ones(n)
    a, b = min(n, int(fade_in * sr)), min(n, int(fade_out * sr))
    env[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    env[n - b :] *= np.cos(np.linspace(0, np.pi / 2, b)) ** 2
    return env


def render(cfg: CompositionConfig) -> RenderResult:
    """Render the full piece described by ``cfg`` (deterministic for a given seed)."""
    sr = cfg.sample_rate
    gammas = load_zeros(max(cfg.max_zeros, 1))
    tl = build_timeline(cfg)
    log.info("timeline: %.1fs, %d control frames, up to %d zeros", cfg.duration, tl.t.size, gammas.size)
    sal = salience_curve(tl.x, tl.n_zeros, gammas, cfg.taper)
    events = [e for e in detect_events(tl, sal, cfg) if tl.pluck_gain[min(int(e.time * tl.rate), tl.t.size - 1)] > 0.02]
    log.info("events: %d", len(events))

    tail = 4.0  # let the reverb and the last notes ring
    n_audio = int((cfg.duration + tail) * sr)
    tl_pad = _pad_timeline(tl, int(tail * tl.rate))
    sal_pad = np.concatenate([sal, np.zeros(tl_pad.t.size - sal.size)])

    m = cfg.mix
    drone = _render_drone(cfg, tl_pad, gammas, n_audio)
    plucks, bells = _render_notes(cfg, tl_pad, events, n_audio)
    breath = _render_breath(cfg, tl_pad, sal_pad, n_audio)
    pole = _render_pole(cfg, n_audio)

    def norm(a: FloatArray) -> FloatArray:
        peak = float(np.max(np.abs(a)))
        return a / peak if peak > 0 else a

    mix = (
        synth.db_to_amp(m.drone_db) * norm(drone)
        + synth.db_to_amp(m.pluck_db) * norm(plucks)
        + synth.db_to_amp(m.bell_db) * norm(bells)
        + synth.db_to_amp(m.breath_db) * norm(breath)
        + synth.db_to_amp(m.pole_db) * norm(pole)
    )
    mix *= _fades(n_audio, sr)[:, None]
    mix = synth.reverb(mix, sr, np.random.default_rng(cfg.seed + 4), t60=m.reverb_t60, mix=m.reverb_mix)
    mix = synth.master(mix, sr, peak_db=m.peak_db)
    return RenderResult(mix, sr, events, tl, sal)


def _pad_timeline(tl: Timeline, n: int) -> Timeline:
    def pad(a: NDArray, value: float | None = None) -> NDArray:
        fill = a[-1] if value is None else value
        return np.concatenate([a, np.full(n, fill, dtype=a.dtype)])

    return Timeline(
        rate=tl.rate,
        t=np.arange(tl.t.size + n) / tl.rate,
        x=pad(tl.x),
        n_zeros=pad(tl.n_zeros),
        section=pad(tl.section),
        drone_gain=synth.smooth(pad(tl.drone_gain, 0.0), tl.rate, 0.5),
        pluck_gain=pad(tl.pluck_gain, 0.0),
        breath_gain=pad(tl.breath_gain, 0.0),
    )


def write_outputs(result: RenderResult, cfg: CompositionConfig, out_dir: Path, stem: str) -> dict[str, Path]:
    """Write WAV (24-bit), event list (JSON) and MIDI; returns paths written."""
    import soundfile as sf

    from .midi import write_midi

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "wav": out_dir / f"{stem}.wav",
        "events": out_dir / f"{stem}.events.json",
        "midi": out_dir / f"{stem}.mid",
    }
    sf.write(paths["wav"], result.audio, result.sample_rate, subtype="PCM_24")
    meta = {
        "title": cfg.title,
        "duration_s": result.audio.shape[0] / result.sample_rate,
        "stats": result.stats(),
        "sections": [asdict(s) for s in cfg.sections],
        "events": [asdict(e) | {"prime": e.prime} for e in result.events],
    }
    paths["events"].write_text(json.dumps(meta, indent=1))
    write_midi(result.events, paths["midi"], cfg)
    return paths
