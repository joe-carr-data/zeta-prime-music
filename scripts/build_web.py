"""Build the self-contained web demo: inject the first 200 zeta zeros into web/hear-the-primes.src.html."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from zeta_music.zeros import load_zeros

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "/*__ZEROS__*/[]"


def build(out: Path, n: int = 200) -> Path:
    src = (ROOT / "web" / "hear-the-primes.src.html").read_text()
    if PLACEHOLDER not in src:
        raise SystemExit("placeholder for zeros not found in web source")
    zeros = json.dumps([round(float(g), 9) for g in load_zeros(n)])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src.replace(PLACEHOLDER, zeros))
    return out


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "output" / "web" / "hear-the-primes.html"))
