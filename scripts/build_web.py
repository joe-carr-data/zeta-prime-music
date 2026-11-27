"""Build the self-contained web demo: inject the first 200 zeta zeros into web/hear-the-primes.src.html."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from zeta_music.zeros import load_zeros

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "/*__ZEROS__*/[]"


STANDALONE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
"""
BACK_LINK = (
    '<p style="max-width:1040px;margin:0 auto;padding:14px max(16px,env(safe-area-inset-left,0px)) 0;'
    'font:500 14px Inter,system-ui,sans-serif"><a href="./" style="color:inherit">&larr; Zeta Prime Music</a></p>'
)


def build(out: Path, n: int = 200, standalone: bool = False) -> Path:
    """Write the demo. ``standalone`` wraps it in a full HTML document (for the GitHub Pages site)."""
    src = (ROOT / "web" / "hear-the-primes.src.html").read_text()
    if PLACEHOLDER not in src:
        raise SystemExit("placeholder for zeros not found in web source")
    zeros = json.dumps([round(float(g), 9) for g in load_zeros(n)])
    out.parent.mkdir(parents=True, exist_ok=True)
    html = src.replace(PLACEHOLDER, zeros)
    if standalone:
        head, _, body = html.partition("</style>")
        html = STANDALONE_HEAD + head + "</style>\n</head>\n<body>\n" + BACK_LINK + body + "\n</body>\n</html>\n"
    out.write_text(html)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--standalone"]
    target = Path(args[0]) if args else ROOT / "output" / "web" / "hear-the-primes.html"
    print(build(target, standalone="--standalone" in sys.argv))
