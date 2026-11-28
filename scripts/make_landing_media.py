"""Build the landing-page media from the rendered visualiser videos of *The Sound of the Primes*.

1. ``compare-2-200.mp4``: the same 8-second bar of the number line twice, first with 2 zeros
   (track 0:24-0:32), then with 200 zeros (track 1:12-1:20), with a large pass badge.
2. ``sound-of-the-primes-60s.mp4``: the vertical clip (track 0:24-1:28) with timed captions in the
   empty space below the curve.

Usage::

    uv run python scripts/make_landing_media.py --full output/proposals/J2_video/J_full.mp4 \\
        --vertical output/proposals/J2_video/J_6_the_story.mp4 --out docs/media

Needs ffmpeg; captions are drawn with Pillow (no ffmpeg text filter required).
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_TEXT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
INK = (233, 230, 223, 255)
ACCENT = (45, 212, 191, 255)
YELLOW = (242, 201, 76, 255)
PANEL = (10, 14, 22, 215)

# (start, end) in seconds of the track; every bar of "Tuning in" is 8 s long and starts at 16 s
PASS_2 = (24.0, 32.0)
PASS_200 = (72.0, 80.0)
# captions on the vertical clip, in clip time (the clip starts at track 0:24)
#   clip 0-8 s: 2 zeros, 8-16: 3, 16-24: 5, 24-32: 8, 32-40: 13, 40-48: 34, 48-56: 200, 56-64: 500
#   (the opening caption from `zeta-music video --caption` covers 0-4 s)
VERTICAL_CAPTIONS = [
    (4.3, 7.8, "Watch where the piano notes land.", "2 zeros: only a few hit primes."),
    (32.3, 39.8, "13 zeros:", "more primes come into focus."),
    (48.2, 55.8, "200 zeros: 7 gets the piano,", "9 = 3² gets the vibraphone."),
]


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def badge(w: int, h: int, step: str, label: str, colour: tuple[int, int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f1, f2 = _font(FONT_BOLD, 26), _font(FONT_BOLD, 44)
    x, y = 36, 28
    d.rounded_rectangle((x - 18, y - 14, x + 330, y + 96), 14, fill=PANEL)
    d.text((x, y), step, font=f1, fill=INK)
    d.text((x, y + 34), label, font=f2, fill=colour)
    return img


def caption(w: int, h: int, line1: str, line2: str) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = _font(FONT_TEXT, 40)
    lines = [line1, line2]
    widths = [d.textlength(s, font=f) for s in lines]
    box_w, line_h = max(widths) + 56, 54
    y0 = int(h * 0.865)
    x0 = (w - box_w) / 2
    d.rounded_rectangle((x0, y0, x0 + box_w, y0 + line_h * 2 + 28), 16, fill=PANEL)
    for i, (s, tw) in enumerate(zip(lines, widths, strict=True)):
        d.text(((w - tw) / 2, y0 + 14 + i * line_h), s, font=f, fill=YELLOW if i == 0 else INK)
    return img


def _size(video: Path) -> tuple[int, int]:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    w, h = out.split(",")
    return int(w), int(h)


def _run(cmd: list[str]) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *cmd], check=True)


ENCODE = [
    "-c:v",
    "libx264",
    "-preset",
    "slow",
    "-crf",
    "26",
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    "aac",
    "-b:a",
    "160k",
    "-movflags",
    "+faststart",
]


def comparison(full: Path, out: Path, tmp: Path) -> Path:
    w, h = _size(full)
    b1, b2 = tmp / "b1.png", tmp / "b2.png"
    badge(w, h, "FIRST PASS", "2 zeros", INK).save(b1)
    badge(w, h, "SAME BAR, AGAIN", "200 zeros", YELLOW).save(b2)
    (a0, a1), (c0, c1) = PASS_2, PASS_200
    fade = 0.12  # short audio fades so the cut does not click
    graph = (
        f"[0:v]trim={a0}:{a1},setpts=PTS-STARTPTS[v1];[0:a]atrim={a0}:{a1},asetpts=PTS-STARTPTS,"
        f"afade=t=in:d={fade},afade=t=out:st={a1 - a0 - fade}:d={fade}[a1];"
        f"[0:v]trim={c0}:{c1},setpts=PTS-STARTPTS[v2];[0:a]atrim={c0}:{c1},asetpts=PTS-STARTPTS,"
        f"afade=t=in:d={fade},afade=t=out:st={c1 - c0 - 0.6}:d=0.6[a2];"
        "[v1][1:v]overlay=shortest=1[v1b];[v2][2:v]overlay=shortest=1[v2b];"
        "[v1b][a1][v2b][a2]concat=n=2:v=1:a=1[v][a]"
    )
    _run(
        [
            "-i",
            str(full),
            "-loop",
            "1",
            "-i",
            str(b1),
            "-loop",
            "1",
            "-i",
            str(b2),
            "-filter_complex",
            graph,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            str((a1 - a0) + (c1 - c0)),
            *ENCODE,
            str(out),
        ]
    )
    _run(["-ss", "12", "-i", str(out), "-frames:v", "1", "-q:v", "4", str(out.with_name(out.stem + "-poster.jpg"))])
    return out


def captioned_vertical(vertical: Path, out: Path, tmp: Path) -> Path:
    w, h = _size(vertical)
    inputs: list[str] = ["-i", str(vertical)]
    chain, last = [], "0:v"
    for i, (t0, t1, l1, l2) in enumerate(VERTICAL_CAPTIONS, start=1):
        png = tmp / f"cap{i}.png"
        caption(w, h, l1, l2).save(png)
        inputs += ["-loop", "1", "-i", str(png)]
        chain.append(f"[{last}][{i}:v]overlay=enable='between(t,{t0},{t1})':shortest=1[c{i}]")
        last = f"c{i}"
    _run([*inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a", *ENCODE, str(out)])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--full", type=Path, required=True, help="16:9 visualiser of the whole track")
    ap.add_argument("--vertical", type=Path, required=True, help="9:16 clip of track 0:24-1:28")
    ap.add_argument("--out", type=Path, default=Path("docs/media"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        print(comparison(args.full, args.out / "compare-2-200.mp4", tmp))
        print(captioned_vertical(args.vertical, args.out / "sound-of-the-primes-60s.mp4", tmp))


if __name__ == "__main__":
    main()
