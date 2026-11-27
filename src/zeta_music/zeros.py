"""Access to the imaginary parts of the nontrivial zeros of the Riemann zeta function.

Every nontrivial zero is assumed (Riemann Hypothesis, verified numerically far beyond
anything used here) to have the form ``rho = 1/2 + i*gamma``. Zeros come in conjugate
pairs, so we only store the positive ordinates ``gamma_1 < gamma_2 < ...``.

The first 500 ordinates ship with the package (computed with :func:`mpmath.zetazero`).
More can be computed on demand and are cached on disk.
"""

from __future__ import annotations

import os
from functools import lru_cache
from importlib import resources
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

__all__ = ["BUNDLED_COUNT", "compute_zeros", "load_zeros"]

BUNDLED_COUNT = 500
_CACHE_ENV = "ZETA_MUSIC_CACHE"


def _cache_dir() -> Path:
    base = os.environ.get(_CACHE_ENV)
    path = Path(base) if base else Path.home() / ".cache" / "zeta-music"
    path.mkdir(parents=True, exist_ok=True)
    return path


@lru_cache(maxsize=1)
def _bundled() -> NDArray[np.float64]:
    text = resources.files("zeta_music.data").joinpath("zeros.txt").read_text()
    values = [float(line) for line in text.splitlines() if line and not line.startswith("#")]
    arr = np.asarray(values, dtype=np.float64)
    if arr.size != BUNDLED_COUNT or not np.all(np.diff(arr) > 0):
        raise RuntimeError("bundled zeros file is corrupt")
    return arr


def compute_zeros(start: int, stop: int, dps: int = 20) -> NDArray[np.float64]:
    """Compute ordinates ``gamma_n`` for ``start <= n < stop`` (1-based) with mpmath."""
    if start < 1 or stop < start:
        raise ValueError(f"invalid zero index range [{start}, {stop})")
    import mpmath as mp

    with mp.workdps(dps):
        return np.array([float(mp.zetazero(n).imag) for n in range(start, stop)], dtype=np.float64)


def load_zeros(n: int) -> NDArray[np.float64]:
    """Return the first ``n`` positive ordinates ``gamma_1..gamma_n`` (ascending).

    Uses bundled data for ``n <= 500``; beyond that, computes the missing zeros once and
    caches them in ``$ZETA_MUSIC_CACHE`` (default ``~/.cache/zeta-music``).
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    bundled = _bundled()
    if n <= bundled.size:
        return bundled[:n].copy()

    cache = _cache_dir() / "zeros_extra.npy"
    extra = np.load(cache) if cache.exists() else np.empty(0)
    have = bundled.size + extra.size
    if n > have:
        more = compute_zeros(have + 1, n + 1)
        extra = np.concatenate([extra, more])
        tmp = cache.with_suffix(".tmp.npy")
        np.save(tmp, extra)
        tmp.replace(cache)
    return np.concatenate([bundled, extra])[:n]
