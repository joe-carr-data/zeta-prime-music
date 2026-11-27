"""Hero animation for the README: the primes appearing as zeta zeros are added (needs ``plot`` + ffmpeg).

Every frame is computed from the explicit formula, nothing is drawn by hand:

* the bright curve is the normalised spike curve ψ'_N(x) for the current number of zeros N;
* the faint wave behind it is the newest zero's own oscillation cos(γ_N ln x);
* a prime lights up (and stays lit) once a peak sits on it within the resolution of N zeros;
  prime powers light up fainter, as in the music.

N grows geometrically from 1 to 200, holds, then the loop fades and restarts.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

from .composition import salience_curve
from .explicit import prime_powers
from .zeros import load_zeros

__all__ = ["HeroSpec", "hero_schedule", "render_hero"]

log = logging.getLogger(__name__)

BG = "#0a0e16"
INK = "#e9e6df"
MUTED = "#7d8796"
GRIDC = "#161d2a"
PRIME = "#ff7a59"
POWER = "#6aa8ff"
WAVE = "#2dd4bf"


@dataclass(frozen=True)
class HeroSpec:
    width: int = 960
    height: int = 480
    fps: int = 24
    grow: float = 8.0  # seconds for N: 1 -> max
    hold: float = 2.5  # seconds at max
    fade: float = 0.75  # seconds fade-out before looping
    max_zeros: int = 200
    x0: float = 1.5
    x1: float = 31.5


def hero_schedule(spec: HeroSpec) -> np.ndarray:
    """Zero count (float) for every frame: geometric growth, hold, then fade frames at max."""
    n_grow = int(spec.grow * spec.fps)
    n_rest = int((spec.hold + spec.fade) * spec.fps)
    grow = spec.max_zeros ** (np.arange(n_grow) / max(n_grow - 1, 1))
    return np.concatenate([grow, np.full(n_rest, float(spec.max_zeros))])


def render_hero(out_gif: Path, spec: HeroSpec = HeroSpec(), out_mp4: Path | None = None) -> Path:
    """Render the looping hero animation to a palette-optimised GIF (and optionally an MP4)."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gammas = load_zeros(spec.max_zeros)
    xs = np.linspace(spec.x0, spec.x1, 1500)
    pps = [pp for pp in prime_powers(spec.x1) if pp.n >= 2]
    schedule = hero_schedule(spec)
    n_frames = schedule.size
    fade_start = n_frames - int(spec.fade * spec.fps)

    w, h = spec.width, spec.height
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=BG)
    ax = fig.add_axes((0.04, 0.17, 0.92, 0.60), facecolor=BG)
    ax.set_xlim(spec.x0, spec.x1)
    ax.set_ylim(-1.55, 1.75)  # lanes: curve above 0, number labels at -0.62, newest wave at -1.2
    ax.axis("off")
    for pp in pps:  # where the primes really are
        ax.axvline(pp.n, color=GRIDC, lw=1.0, zorder=0)
    ax.axhline(-0.32, color=GRIDC, lw=1.0, zorder=0)
    (wave,) = ax.plot([], [], color=WAVE, lw=1.2, alpha=0.35, zorder=1)
    (glow,) = ax.plot([], [], color=INK, lw=5.0, alpha=0.10, zorder=2, solid_capstyle="round")
    (curve,) = ax.plot([], [], color=INK, lw=1.7, zorder=3, solid_joinstyle="round")
    labels = {
        pp.n: ax.text(pp.n, -0.5, str(pp.n), ha="center", va="top", fontsize=12 if pp.is_prime else 10,
                      color=MUTED, alpha=0.35, weight="bold" if pp.is_prime else "normal", zorder=4)
        for pp in pps
    }  # fmt: skip
    fig.text(0.04, 0.90, "Zeta Prime Music", color=INK, fontsize=24, weight="bold", va="center")
    fig.text(0.04, 0.83, "each zero of ζ(s) is a wave — add them and the primes appear",
             color=MUTED, fontsize=11.5, va="center")  # fmt: skip
    counter = fig.text(0.96, 0.90, "", color=WAVE, fontsize=22, ha="right", va="center", family="monospace")
    sub = fig.text(0.96, 0.83, "", color=MUTED, fontsize=11, ha="right", va="center", family="monospace")
    fig.text(0.04, 0.07, r"$\psi'(x) = 1 - 2x^{-1/2}\sum_{\gamma}\cos(\gamma\ln x)$", color=MUTED, fontsize=13,
             va="center")  # fmt: skip
    fig.text(0.96, 0.07, "primes", color=PRIME, fontsize=11, ha="right", va="center", weight="bold")
    fig.text(0.875, 0.07, "prime powers", color=POWER, fontsize=11, ha="right", va="center")

    lit: dict[int, float] = {}  # prime power -> frame it lit up
    seen_at: dict[int, float] = {}  # prime power -> last frame its peak was resolved
    with tempfile.TemporaryDirectory() as tmp:
        mp4 = Path(tmp) / "hero.mp4"
        cmd = [
            "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
            "-r", str(spec.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(mp4),
        ]  # fmt: skip
        with subprocess.Popen(cmd, stdin=subprocess.PIPE) as proc:
            assert proc.stdin is not None
            try:
                for f, n in enumerate(schedule):
                    s = salience_curve(xs, np.full(xs.size, n), gammas)
                    # soft compression keeps tall spikes and deep troughs in their lane, no flat tops
                    y = np.where(s > 0, 1.45 * np.tanh(s / 1.45), 0.3 * np.tanh(s / 0.3))
                    curve.set_data(xs, y)
                    glow.set_data(xs, y)
                    k = min(int(np.ceil(n)) - 1, gammas.size - 1)
                    wave.set_data(xs, -1.22 + 0.2 * np.cos(gammas[k] * np.log(xs)))
                    counter.set_text(f"N = {round(n):>3}")
                    sub.set_text(f"newest  γ{k + 1} = {gammas[k]:.3f}")
                    peaks, _ = find_peaks(s, prominence=0.18, height=0.18)
                    tol = 0.5 * xs[peaks] * np.pi / (14.0 + 2.2 * n)
                    resolved = set()
                    for xp, t in zip(xs[peaks], tol, strict=True):
                        m = round(xp)
                        if m in labels and abs(xp - m) <= min(0.25, t):
                            resolved.add(m)
                    for m in resolved:  # lit while resolved; remember when it first lit for the pop
                        lit.setdefault(m, f)
                    seen_at.update(dict.fromkeys(resolved, f))
                    for m in list(lit):  # unlit after 0.3 s without a resolved peak (no flicker)
                        if f - seen_at.get(m, -1e9) > 0.3 * spec.fps:
                            del lit[m]
                    for pp in pps:
                        lab = labels[pp.n]
                        if pp.n in lit:
                            age = (f - lit[pp.n]) / spec.fps
                            lab.set_color(PRIME if pp.is_prime else POWER)
                            lab.set_alpha(1.0 if pp.is_prime else 0.8)
                            lab.set_fontsize((12 if pp.is_prime else 10) * (1.0 + 0.35 * max(0.0, 1 - age / 0.4)))
                        else:
                            lab.set_color(MUTED)
                            lab.set_alpha(0.35)
                            lab.set_fontsize(12 if pp.is_prime else 10)
                    fig.canvas.draw()
                    frame = np.asarray(fig.canvas.buffer_rgba()).copy()
                    if f >= fade_start:  # fade to the background colour so the loop restarts cleanly
                        a = 1.0 - (f - fade_start + 1) / (n_frames - fade_start)
                        bg = np.array([10, 14, 22, 255], dtype=np.float32)
                        frame = (frame.astype(np.float32) * a + bg * (1 - a)).astype(np.uint8)
                    proc.stdin.write(frame.tobytes())
            finally:
                proc.stdin.close()
                plt.close(fig)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed (exit {proc.returncode})")
        out_gif.parent.mkdir(parents=True, exist_ok=True)
        palette = Path(tmp) / "palette.png"
        gif_w = min(w, 720)
        filt = f"fps={min(spec.fps, 15)},scale={gif_w}:-1:flags=lanczos"
        gen = f"{filt},palettegen=max_colors=64:stats_mode=diff"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", gen, str(palette)], check=True)
        use = f"{filt}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-i", str(palette), "-lavfi", use,
                        "-loop", "0", str(out_gif)], check=True)  # fmt: skip
        if out_mp4 is not None:
            out_mp4.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(mp4, out_mp4)
    log.info("hero animation: %d frames -> %s", n_frames, out_gif)
    return out_gif
