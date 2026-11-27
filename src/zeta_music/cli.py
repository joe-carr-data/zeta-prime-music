"""Command-line interface: ``zeta-music {render,literal,explain,video,animate,produce,produce-preset,zeros}``."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

__all__ = ["main"]


def _cmd_render(args: argparse.Namespace) -> int:
    from .composition import render, write_outputs
    from .config import load_config

    cfg = load_config(args.config)
    t0 = time.perf_counter()
    result = render(cfg, stems=args.stems)
    stem = args.name or Path(args.config).stem
    paths = write_outputs(result, cfg, Path(args.out), stem)
    if not args.no_plot:
        try:
            from .plots import plot_score

            paths["score_png"] = plot_score(result, Path(args.out) / f"{stem}.score.png")
        except ImportError:
            logging.warning("matplotlib not installed; skipping score plot (pip install zeta-music[plot])")
    print(f"rendered '{cfg.title}' ({cfg.duration:.0f}s) in {time.perf_counter() - t0:.1f}s; events: {result.stats()}")
    for kind, p in paths.items():
        print(f"  {kind:10s} {p}")
    return 0


def _cmd_literal(args: argparse.Namespace) -> int:
    import soundfile as sf

    from .literal import literal

    y = literal(args.mode, args.zeros, args.duration, args.sr, args.base_hz, args.x_start, args.x_end)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, y, args.sr, subtype="PCM_24")
    print(out)
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    from .plots import plot_explainer

    print(plot_explainer(Path(args.out), args.zeros, args.xmax))
    return 0


def _cmd_video(args: argparse.Namespace) -> int:
    from .config import load_score_config
    from .video import VideoSpec, render_video

    cfg, produce = load_score_config(args.config)  # a produced version's score keeps its [produce] table
    spec = VideoSpec(
        aspect=args.aspect,
        fps=args.fps,
        start=args.start,
        end=args.end,
        caption=args.caption,
        end_card=args.end_card,
        title=args.title,
    )
    print(render_video(cfg, Path(args.audio), Path(args.out), spec, produce=produce))
    return 0


def _cmd_animate(args: argparse.Namespace) -> int:
    from .animate import HeroSpec, render_hero

    spec = HeroSpec(width=args.width, height=args.width // 2, fps=args.fps)
    print(render_hero(Path(args.out), spec, Path(args.mp4) if args.mp4 else None))
    return 0


def _cmd_produce(args: argparse.Namespace) -> int:
    from .produce import produce

    t0 = time.perf_counter()
    tunings = ("just", "tempered") if args.tuning == "both" else (args.tuning,)
    meta = produce(
        Path(args.score),
        Path(args.out),
        tunings,
        soundfont=args.soundfont,
        audio=not args.midi_only,
        name=args.name,
        stem_format=args.stem_format,
    )
    print(f"produced '{meta['title']}' in {time.perf_counter() - t0:.1f}s; notes: {meta['notes']}")
    for tuning, rep in meta.get("reports", {}).items():
        m = rep["master"]
        print(f"  {tuning:9s} {m['integrated_lufs']} LUFS integrated, {m['true_peak_dbtp']} dBTP")
    for kind, p in meta["paths"].items():
        if not kind.startswith(("stem_", "midi_just_")):
            print(f"  {kind:24s} {p}")
    return 0


def _cmd_produce_preset(args: argparse.Namespace) -> int:
    from .produce import save_plugin_state

    print(save_plugin_state(args.plugin, Path(args.out), plugin_name=args.plugin_name, state=args.state))
    return 0


def _cmd_zeros(args: argparse.Namespace) -> int:
    from .zeros import load_zeros

    for i, g in enumerate(load_zeros(args.n), 1):
        print(f"{i:5d}  1/2 + {g:.12f} i")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zeta-music", description="The music of the primes, from the zeros of ζ(s).")
    from . import __version__

    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render a composition from a TOML score")
    r.add_argument("config", help="path to composition TOML")
    r.add_argument("-o", "--out", default="output")
    r.add_argument("--name", help="output file stem (default: config stem)")
    r.add_argument("--no-plot", action="store_true")
    r.add_argument("--stems", action="store_true", help="also write dry stems (drone, plucks, bells, breath, pole)")
    r.set_defaults(func=_cmd_render)

    lit = sub.add_parser("literal", help="direct sonification of the explicit-formula sum")
    lit.add_argument("mode", choices=["log", "linear"])
    lit.add_argument("-o", "--out", default="output/literal.wav")
    lit.add_argument("-n", "--zeros", type=int, default=200)
    lit.add_argument("-d", "--duration", type=float, default=10.0)
    lit.add_argument("--sr", type=int, default=44100)
    lit.add_argument("--base-hz", type=float, default=110.0)
    lit.add_argument("--x-start", type=float, default=1.5)
    lit.add_argument("--x-end", type=float, default=400.0)
    lit.set_defaults(func=_cmd_literal)

    e = sub.add_parser("explain", help="plot the video's argument (needs matplotlib)")
    e.add_argument("-o", "--out", default="output/explainer.png")
    e.add_argument("-n", "--zeros", type=int, default=200)
    e.add_argument("--xmax", type=float, default=30.0)
    e.set_defaults(func=_cmd_explain)

    v = sub.add_parser("video", help="visualiser video synced to a rendered WAV (needs matplotlib + ffmpeg)")
    v.add_argument("config", help="the score TOML the audio was rendered from (render or produce)")
    v.add_argument("--audio", required=True, help="rendered WAV")
    v.add_argument("-o", "--out", default="output/video.mp4")
    v.add_argument("--aspect", choices=["16:9", "9:16", "1:1"], default="16:9")
    v.add_argument("--fps", type=int, default=30)
    v.add_argument("--start", type=float, default=0.0, help="clip start (s)")
    v.add_argument("--end", type=float, default=None, help="clip end (s)")
    v.add_argument("--caption", default=None, help="hook text shown over the first 4 s")
    v.add_argument("--end-card", action="store_true", help="title card with the site address over the last 2.5 s")
    v.add_argument("--title", default=None, help="page title (default: the score's title)")
    v.set_defaults(func=_cmd_video)

    an = sub.add_parser("animate", help="README hero animation: the primes appearing as zeros are added")
    an.add_argument("-o", "--out", default="docs/media/hero.gif")
    an.add_argument("--mp4", default=None, help="also save the full-quality MP4 here")
    an.add_argument("--width", type=int, default=960)
    an.add_argument("--fps", type=int, default=24)
    an.set_defaults(func=_cmd_animate)

    pr = sub.add_parser("produce", help="produced version: tempo-mapped MIDI, instruments, stems, mastered WAV/M4A")
    pr.add_argument("score", help="score TOML with a [produce] table")
    pr.add_argument("-o", "--out", default="output/commercial")
    pr.add_argument("--name", help="output file stem (default: score stem)")
    pr.add_argument("--tuning", choices=["just", "tempered", "both"], default="both", help="audio render(s)")
    pr.add_argument("--soundfont", help="SoundFont for instrument = 'sf2' voices (else $ZETA_SOUNDFONT or the score's)")
    pr.add_argument("--midi-only", action="store_true", help="write the MIDI files and event list only")
    pr.add_argument("--stem-format", choices=["flac", "wav"], default="flac", help="24-bit stems (default flac)")
    pr.set_defaults(func=_cmd_produce)

    pp = sub.add_parser("produce-preset", help="open an AU/VST3 plugin's editor, then save its state for a score")
    pp.add_argument("--plugin", required=True, help="path to the .vst3 or .component")
    pp.add_argument("--plugin-name", help="plugin inside a multi-plugin bundle")
    pp.add_argument("--state", help="existing state file to start from")
    pp.add_argument("--out", required=True, help="where to save the plugin state")
    pp.set_defaults(func=_cmd_produce_preset)

    z = sub.add_parser("zeros", help="print the first n nontrivial zeros")
    z.add_argument("n", type=int, nargs="?", default=10)
    z.set_defaults(func=_cmd_zeros)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    try:
        return int(args.func(args))
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
