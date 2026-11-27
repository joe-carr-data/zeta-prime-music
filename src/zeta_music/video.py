"""Visualiser video: the spike curve forming in sync with the music (requires the ``plot`` extra + ffmpeg).

Each frame shows the salience curve ψ'_N(x) (normalised) over the bar currently being played,
with the active number of zeros N. The part of the curve already swept by the playhead is drawn
bright, the rest dim; every note that sounds is labelled with its integer as it is struck
(primes red, prime powers blue, ghosts grey). Frames are piped straight into ffmpeg and muxed
with the rendered audio, so ``--start/--end`` cut social clips from the same render.

For a produced version (a score with a ``[produce]`` table, rendered by ``zeta-music produce``)
pass the table as ``produce``: the notes and their times are the engine's, as in the produced
audio, and a section whose arrangement silences the primes (or bells) labels none of them.
"""

from __future__ import annotations

import logging
import math
import shutil
import subprocess
import tempfile
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from .composition import Event, Timeline, analyse, salience_curve
from .config import CompositionConfig

__all__ = ["VideoSpec", "frame_count", "produced_levels", "render_video"]

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
    caption: str | None = None  # hook shown over the first CAPTION_SECONDS of the clip
    end_card: bool = False  # title card over the last END_CARD_SECONDS
    title: str | None = None  # page title (default: the score's title)


CAPTION_SECONDS = 4.0
PORTRAIT_WINDOW = 28.0  # narrower sliding window on vertical video: twin-prime labels stay apart
CAPTION_CHARS = {True: 30, False: 72}  # characters per caption line: portrait, landscape
END_CARD_SECONDS = 2.5
END_CARD_TITLE = "Zeta Prime Music"
END_CARD_URL = "joe-carr-data.github.io/zeta-prime-music"


# The produced voice that plays each kind of note (ghosts are played by the primes voice).
PRODUCED_VOICE = {"prime": "primes", "ghost": "primes", "prime_power": "bells"}


def produced_levels(produce: Mapping[str, Any], cfg: CompositionConfig) -> dict[str, dict[str, float]]:
    """Per section, the arrangement level of the voices that play labelled notes (0 = silent).

    Mirrors the producer: a voice missing from ``[produce.voices]``, or from a section's
    ``[produce.arrangement."<section>"]`` table, does not play there.
    """
    voices = produce.get("voices", {})
    arrangement = produce.get("arrangement", {})
    if not isinstance(voices, Mapping) or not isinstance(arrangement, Mapping):
        raise ValueError("[produce.voices] and [produce.arrangement] must be tables")
    names = [s.name for s in cfg.sections]
    unknown = sorted(set(arrangement) - set(names))
    if unknown:
        raise ValueError(f"[produce.arrangement] sections not in the score: {unknown}")
    out: dict[str, dict[str, float]] = {}
    for name in names:
        table = arrangement.get(name, {})
        if not isinstance(table, Mapping):
            raise ValueError(f"[produce.arrangement.{name!r}] must be a table")
        levels: dict[str, float] = {}
        for voice in sorted(set(PRODUCED_VOICE.values())):
            v = table.get(voice, 0.0)
            if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
                raise ValueError(f"[produce.arrangement.{name!r}] {voice} must be a number, got {v!r}")
            levels[voice] = float(v) if voice in voices else 0.0
        out[name] = levels
    return out


def _produced_events(
    events: list[Event], cfg: CompositionConfig, tl: Timeline, produce: Mapping[str, Any]
) -> list[Event]:
    """The events the produced arrangement actually plays."""
    levels = produced_levels(produce, cfg)

    def section(e: Event) -> str:
        return cfg.sections[int(tl.section[min(int(e.time * tl.rate), tl.t.size - 1)])].name

    return [e for e in events if levels[section(e)][PRODUCED_VOICE[e.kind]] > 0]


def wrap_caption(text: str, portrait: bool) -> str:
    """Break a caption into lines that, boxed, stay inside the frame (matplotlib's own wrap
    fills the whole figure width, so the box ran off the edges of a vertical clip)."""
    return textwrap.fill(text, width=CAPTION_CHARS[portrait], break_long_words=False)


LABEL_EM = 0.62 * 100 / 72  # px per pt of font size per character (bold digits at dpi 100), approx.
LABEL_LIFT = 0.24  # data units a label moves up per row when it would touch its neighbour


def label_rows(xs: list[float], widths: list[float], gap_frac: float = 0.15, max_rows: int = 2) -> list[int]:
    """Row (0 = normal height, 1 = lifted, …) for each centred label so neighbours never touch:
    going left to right, a label takes the lowest row whose previous label it clears."""
    rows = [0] * len(xs)
    right_edge = [-math.inf] * max_rows
    for i in sorted(range(len(xs)), key=lambda k: xs[k]):
        left = xs[i] - widths[i] * (0.5 + gap_frac)
        row = next((r for r in range(max_rows) if left >= right_edge[r]), 0)
        rows[i] = row
        right_edge[row] = xs[i] + widths[i] * (0.5 + gap_frac)
    return rows


def _window(cfg: CompositionConfig, sec_idx: int, x_now: float, width: float = 40.0) -> tuple[float, float]:
    """Visible x range: the whole section if short or looping, else a ``width``-wide window that leads
    in the direction of travel (85 % behind the playhead, 15 % ahead), clamped to the section."""
    sec = cfg.sections[sec_idx]
    lo, hi = sorted((sec.x_start, sec.x_end))
    if sec.loop or hi - lo <= width:
        return lo, hi
    if sec.x_end >= sec.x_start:  # ascending: most of the window behind (left of) the playhead
        start = min(max(lo, x_now - 0.85 * width), hi - width)
    else:  # descending: most of the window behind (right of) the playhead
        start = min(max(lo, x_now - 0.15 * width), hi - width)
    return start, start + width


def _traced(xg: np.ndarray, x_now: float, ascending: bool) -> np.ndarray:
    """Mask of the part of the curve the playhead has already swept."""
    return xg <= x_now if ascending else xg >= x_now


def _ffmpeg_cmd(w: int, h: int, fps: int, audio: Path, start: float, dur: float, crf: int, out: Path) -> list[str]:
    return [
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-ss", f"{start:.6f}", "-t", f"{dur:.6f}", "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf), "-preset", "medium",
        # no output-side -t: the frames we send define the video length (a partial last frame is kept)
        "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out),
    ]  # fmt: skip


def frame_count(duration: float, fps: int) -> int:
    """Frames needed to cover ``duration`` (a partial last frame still counts; at least one)."""
    return max(1, math.ceil(duration * fps - 1e-9))


def render_video(
    cfg: CompositionConfig,
    audio: Path,
    out: Path,
    spec: VideoSpec = VideoSpec(),
    produce: Mapping[str, Any] | None = None,
) -> Path:
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
    import matplotlib.patches
    import matplotlib.pyplot as plt

    if produce is not None:
        produced_levels(produce, cfg)  # fail fast, before the analysis
    gammas, tl, _sal, events = analyse(cfg)
    if produce is not None:
        events = _produced_events(events, cfg, tl, produce)
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
    page_title = spec.title if spec.title is not None else cfg.title
    title = fig.text(0.5, 0.92 if portrait else 0.90, page_title, ha="center", color=FG, fontsize=big, weight="bold",
                     parse_math=False)  # fmt: skip
    subtitle = fig.text(0.5, 0.875 if portrait else 0.84, "", ha="center", color="#9aa0aa", fontsize=big * 0.55)
    counter = fig.text(0.5, 0.82 if portrait else 0.79, "", ha="center", color="#f2c14e", fontsize=big * 0.75)
    formula = r"$\psi'(x) = 1 - 2x^{-1/2}\sum_{\gamma} \cos(\gamma \ln x)$"
    gloss = r"each zero $\rho=\frac{1}{2}+i\gamma$ is a wave; the primes are where they agree"
    formula_line = None  # landscape only: the caption temporarily takes its place
    if portrait:
        fig.text(0.5, 0.20, formula, ha="center", color="#c8c6c3", fontsize=big * 0.6)
        fig.text(0.5, 0.16, gloss, ha="center", color="#9aa0aa", fontsize=big * 0.42)
    else:
        formula_line = fig.text(
            0.5, 0.06, formula + "   —   " + gloss, ha="center", color="#9aa0aa", fontsize=big * 0.45
        )
    labels: list = []
    caption = fig.text(0.5, 0.085 if portrait else 0.055, wrap_caption(spec.caption or "", portrait), ha="center",
                       va="center", color=FG, fontsize=big * 0.62, weight="bold", alpha=0.0, parse_math=False,
                       bbox={"boxstyle": "round,pad=0.6", "fc": "#000000", "ec": "none", "alpha": 0.0})  # fmt: skip
    card = fig.add_axes((0, 0, 1, 1), facecolor=BG)
    card.set_axis_off()
    card.set_zorder(10)  # above the page title, counter and formula
    card.set_alpha(0.0)
    card_bg = card.add_patch(matplotlib.patches.Rectangle((0, 0), 1, 1, transform=card.transAxes, color=BG, alpha=0.0))
    card_title = card.text(0.5, 0.54, END_CARD_TITLE, ha="center", va="center", color=FG, fontsize=big * 1.25,
                           weight="bold", alpha=0.0)  # fmt: skip
    card_url = card.text(0.5, 0.45, END_CARD_URL, ha="center", va="center", color="#2dd4bf", fontsize=big * 0.55,
                         alpha=0.0)  # fmt: skip

    out.parent.mkdir(parents=True, exist_ok=True)
    n_frames = frame_count(end - spec.start, spec.fps)
    cmd = _ffmpeg_cmd(w, h, spec.fps, audio, spec.start, end - spec.start, spec.crf, out)
    cache: dict[tuple[float, float, float], tuple[np.ndarray, np.ndarray]] = {}
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
                lo, hi = _window(cfg, sec_idx, x_now, PORTRAIT_WINDOW if portrait else 40.0)
                key = (n_now, lo, hi)  # exact inputs: identical bars share one curve
                if key not in cache:
                    if len(cache) > 64:
                        cache.clear()
                    xg = np.linspace(max(lo, 1.0001), hi, spec.grid_points)
                    cache[key] = (xg, salience_curve(xg, np.full(xg.size, n_now), gammas, cfg.taper))
                xg, yg = cache[key]
                yc = np.clip(yg, -1.2, 2.4)
                ax.set_xlim(lo, hi)
                dim_line.set_data(xg, yc)
                sec = cfg.sections[sec_idx]
                done = _traced(xg, x_now, sec.x_end >= sec.x_start)
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
                shown = same_bar[-40:]
                styles = []
                for e in shown:
                    age = t - e.time
                    txt = str(e.nearest) if e.kind != "ghost" else f"{e.x:.1f}"
                    styles.append((age, txt, (16 if portrait else 14) * (1.5 if age < 0.12 else 1.0)))
                units_per_px = (hi - lo) / (w * ax.get_position().width)
                base = 16 if portrait else 14  # rows from the resting size: a fresh label's pop does not move them
                widths = [len(txt) * base * LABEL_EM * units_per_px for _a, txt, _s in styles]
                rows = label_rows([e.x for e in shown], widths)
                for e, (age, txt, size), row in zip(shown, styles, rows, strict=True):
                    alpha = 1.0 if age < 0.15 else max(0.6, 1.0 - 0.2 * age)
                    y = min(e.salience, 2.2) + 0.12 + LABEL_LIFT * row
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
                rel, left = t - spec.start, end - t
                if spec.caption:  # fade in over 0.3 s, out over the last 0.5 s of its window
                    a = float(np.clip(min(rel / 0.3, (CAPTION_SECONDS - rel) / 0.5), 0.0, 1.0))
                    caption.set_alpha(a)
                    caption.get_bbox_patch().set_alpha(0.55 * a)
                    if formula_line is not None:  # landscape: the caption takes the formula's line
                        formula_line.set_alpha(1.0 - a)
                if spec.end_card:
                    a = float(np.clip((END_CARD_SECONDS - left) / 0.5, 0.0, 1.0))
                    card_bg.set_alpha(0.92 * a)
                    card_title.set_alpha(a)
                    card_url.set_alpha(a)
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
