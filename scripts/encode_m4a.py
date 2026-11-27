"""Encode every .wav in a folder to 256 kb/s AAC (.m4a) next to it (used by `make proposals`)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main(folder: str) -> int:
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found; skipping .m4a encoding", file=sys.stderr)
        return 0
    for wav in sorted(Path(folder).glob("*.wav")):
        m4a = wav.with_suffix(".m4a")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", "aac", "-b:a", "256k", str(m4a)], check=True
        )
        print(m4a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "output/proposals"))
