"""Visualiser video: the spike curve forming in sync with the music (requires the ``plot`` extra + ffmpeg).

Each frame shows the salience curve ψ'_N(x) (normalised) over the bar currently being played,
with the active number of zeros N. The part of the curve already swept by the playhead is drawn
bright, the rest dim; every note that sounds is labelled with its integer as it is struck
(primes red, prime powers blue, ghosts grey). Frames are piped straight into ffmpeg and muxed
with the rendered audio, so ``--start/--end`` cut social clips from the same render.
"""

from __future__ import annotations

import logging
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from .composition import Event, analyse, salience_curve
from .config import CompositionConfig

__all__ = ["VideoSpec", "frame_count", "render_video"]

log = logging.getLogger(__name__)
Aspect = Literal["16:9", "9:16", "1:1"]
SIZES: dict[str, tuple[int, int]] = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1080, 1080)}
COLORS = {"prime": "#ff5a4f", "prime_power": "#4fa3ff", "ghost": "#8a8f98"}
BG, FG, DIM = "#0d0f14", "#e8e6e3", "#3a3f4b"


@dataclass(frozen=True)
class VideoSpec:
    aspect: Aspect = "16:9"
    fps: int = 30
    start: float = 0.0
    end: float | None = None
    grid_points: int = 900
    crf: int = 20


def _window(cfg: CompositionConfig, sec_idx: int, x_now: float) -> tuple[float, float]:
    sec = cfg.sections[sec_idx]
    lo, hi = sorted((sec.x_start, sec.x_end))
    if sec.loop or hi - lo <= 40:
        return lo, hi
    width = 40.0  # sliding window for long sweeps
    return max(lo, x_now - 0.85 * width), max(lo, x_now - 0.85 * width) + width


def _ffmpeg_cmd(w: int, h: int, fps: int, audio: Path, start: float, dur: float, crf: int, out: Path) -> list[str]:
    return [
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf), "-preset", "medium",
        "-c:a", "aac", "-b:a", "256k", "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out),
    ]  # fmt: skip


def frame_count(duration: float, fps: int) -> int:
    """Frames needed to cover ``duration`` (a partial last frame still counts; at least one)."""
    return max(1, math.ceil(duration * fps - 1e-9))


def render_video(cfg: CompositionConfig, audio: Path, out: Path, spec: VideoSpec = VideoSpec()) -> Path:
    if spec.fps <= 0:
        raise ValueError("fps must be positive")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH")
    import soundfile as sf

    # validate the clip before the (expensive) full-score analysis
    audio_len = sf.info(audio).duration
    end = min(spec.end if spec.end is not None else audio_len, audio_len)
    if not 0 <= spec.start < end:
        raise ValueError(f"invalid clip range [{spec.start}, {end})")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gammas, tl, _sal, events = analyse(cfg)
    seg = tl.segment
    w, h = SIZES[spec.aspect]
    portrait = h > w

    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=BG)
    ax = fig.add_axes((0.06, 0.30, 0.90, 0.48) if portrait else (0.05, 0.16, 0.92, 0.62), facecolor=BG)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(DIM)
    ax.tick_params(colors="#9aa0aa", labelsize=11 if portrait else 10, left=False, labelleft=False)
    ax.set_ylim(-1.2, 2.4)
    (dim_line,) = ax.plot([], [], color=DIM, lw=1.2)
    (live_line,) = ax.plot([], [], color=FG, lw=1.6)
    head = ax.axvline(0, color="#f2c14e", lw=1.0, alpha=0.8)
    big = 30 if portrait else 26
    title = fig.text(0.5, 0.92 if portrait else 0.90, cfg.title, ha="center", color=FG, fontsize=big, weight="bold")
    subtitle = fig.text(0.5, 0.875 if portrait else 0.84, "", ha="center", color="#9aa0aa", fontsize=big * 0.55)
    counter = fig.text(0.5, 0.82 if portrait else 0.79, "", ha="center", color="#f2c14e", fontsize=big * 0.75)
    formula = r"$\psi'(x) = 1 - 2x^{-1/2}\sum_{\gamma} \cos(\gamma \ln x)$"
    gloss = r"each zero $\rho=\frac{1}{2}+i\gamma$ is a wave; the primes are where they agree"
    if portrait:
        fig.text(0.5, 0.20, formula, ha="center", color="#c8c6c3", fontsize=big * 0.6)
        fig.text(0.5, 0.16, gloss, ha="center", color="#9aa0aa", fontsize=big * 0.42)
    else:
        fig.text(0.5, 0.06, formula + "   —   " + gloss, ha="center", color="#9aa0aa", fontsize=big * 0.45)
    labels: list = []

    out.parent.mkdir(parents=True, exist_ok=True)
    n_frames = frame_count(end - spec.start, spec.fps)
    cmd = _ffmpeg_cmd(w, h, spec.fps, audio, spec.start, end - spec.start, spec.crf, out)
    cache: dict[tuple[int, float, float, float], tuple[np.ndarray, np.ndarray]] = {}
    broken = False
    with tempfile.TemporaryFile() as err, subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err) as proc:
        assert proc.stdin is not None
        try:
            for f in range(n_frames):
                t = spec.start + f / spec.fps
                j = min(int(t * tl.rate), tl.t.size - 1)
                sec_idx = int(tl.section[j])
                x_now = float(tl.x[j])
                n_now = float(tl.n_zeros[j])
                lo, hi = _window(cfg, sec_idx, x_now)
                key = (int(seg[j]), round(n_now, 3), round(lo, 2), round(hi, 2))
                if key not in cache:
                    if len(cache) > 64:
                        cache.clear()
                    xg = np.linspace(max(lo, 1.0001), hi, spec.grid_points)
                    cache[key] = (xg, salience_curve(xg, np.full(xg.size, n_now), gammas, cfg.taper))
                xg, yg = cache[key]
                yc = np.clip(yg, -1.2, 2.4)
                ax.set_xlim(lo, hi)
                dim_line.set_data(xg, yc)
                done = xg <= x_now
                live_line.set_data(xg[done], yc[done])
                head.set_xdata([x_now, x_now])
                subtitle.set_text(cfg.sections[sec_idx].name)
                counter.set_text(
                    f"{n_now:.0f} zero{'s' if round(n_now) != 1 else ''}" if n_now >= 1 else "no zeros yet"
                )

                for lab in labels:
                    lab.remove()
                labels = []
                same_bar: list[Event] = [
                    e for e in events if e.time <= t and int(seg[min(int(e.time * tl.rate), seg.size - 1)]) == seg[j]
                ]
                for e in same_bar[-40:]:
                    age = t - e.time
                    alpha = 1.0 if age < 0.15 else max(0.6, 1.0 - 0.2 * age)
                    txt = str(e.nearest) if e.kind != "ghost" else f"{e.x:.1f}"
                    y = min(e.salience, 2.2) + 0.12
                    size = (16 if portrait else 14) * (1.5 if age < 0.12 else 1.0)
                    labels.append(
                        ax.text(
                            e.x,
                            y,
                            txt,
                            ha="center",
                            color=COLORS[e.kind],
                            alpha=alpha,
                            fontsize=size,
                            weight="bold" if e.kind == "prime" else "normal",
                        )
                    )
                fig.canvas.draw()
                proc.stdin.write(fig.canvas.buffer_rgba().tobytes())
                if f % (spec.fps * 10) == 0:
                    log.info("video %.0f%%", 100 * f / max(n_frames, 1))
        except BrokenPipeError:
            broken = True  # the encoder exited early; its exit status and stderr say why
        finally:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                broken = True
            plt.close(fig)
        proc.wait()
        err.seek(0)
        detail = err.read().decode(errors="replace").strip()[-500:]
    if proc.returncode != 0 or broken:
        raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}): {detail or 'no output'}")
    _ = title
    return out
