r"""Riemann/von Mangoldt explicit formulae, evaluated with a finite set of zeros.

The central identity (von Mangoldt, 1895) is

.. math::

    \psi_0(x) = x - \sum_\rho \frac{x^\rho}{\rho} - \log(2\pi) - \tfrac12\log(1 - x^{-2}),

where :math:`\psi(x) = \sum_{p^k \le x} \log p` is Chebyshev's function. Differentiating
formally gives the *prime spike density*

.. math::

    \psi'(x) = \sum_{p^k} \log p\;\delta(x - p^k)
             = 1 - 2x^{-1/2}\sum_{\gamma>0}\cos(\gamma\log x) - \frac{1}{x(x^2-1)},

using :math:`\rho = \tfrac12 + i\gamma` and pairing conjugate zeros (and neglecting the
:math:`1/\rho` vs :math:`1` subtlety absorbed by differentiation). Truncating the sum to
the first *N* zeros gives a smooth curve whose peaks sharpen onto the prime powers as *N*
grows. This is the picture in the video: each zero contributes one oscillation
``x^{-1/2} cos(gamma ln x)``—its "note"—and the primes are the interference pattern.

A smooth spectral taper ``w_k`` (window over the zeros) is optional; it trades peak
sharpness for less Gibbs ringing, exactly like windowing a truncated Fourier series.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "PrimePower",
    "chebyshev_psi",
    "prime_powers",
    "primes_upto",
    "psi_explicit",
    "spike_density",
    "taper_weights",
    "von_mangoldt",
    "zero_contributions",
]

Taper = Literal["none", "hann", "gauss", "fejer"]
FloatArray = NDArray[np.float64]


def primes_upto(n: int) -> NDArray[np.int64]:
    """Sieve of Eratosthenes: all primes ``p <= n``."""
    if n < 2:
        return np.empty(0, dtype=np.int64)
    sieve = np.ones(n + 1, dtype=bool)
    sieve[:2] = False
    for i in range(2, int(n**0.5) + 1):
        if sieve[i]:
            sieve[i * i :: i] = False
    return np.flatnonzero(sieve).astype(np.int64)


@dataclass(frozen=True, slots=True)
class PrimePower:
    """A prime power ``n = p**k`` with its von Mangoldt weight ``log p``."""

    n: int
    p: int
    k: int

    @property
    def weight(self) -> float:
        return float(np.log(self.p))

    @property
    def is_prime(self) -> bool:
        return self.k == 1


def prime_powers(xmax: float) -> list[PrimePower]:
    """All prime powers ``p**k <= xmax`` sorted by value."""
    out: list[PrimePower] = []
    for p in primes_upto(int(xmax)):
        p = int(p)
        q, k = p, 1
        while q <= xmax:
            out.append(PrimePower(q, p, k))
            q *= p
            k += 1
    out.sort(key=lambda pp: pp.n)
    return out


def von_mangoldt(n: int) -> float:
    """Λ(n) = log p if n = p^k, else 0."""
    if n < 2:
        return 0.0
    m = n
    p = 2
    while p * p <= m:
        if m % p == 0:
            while m % p == 0:
                m //= p
            return float(np.log(p)) if m == 1 else 0.0
        p += 1
    return float(np.log(m))  # n itself is prime


def chebyshev_psi(x: ArrayLike) -> FloatArray:
    """Exact Chebyshev ψ(x) = Σ_{n<=x} Λ(n) (step function, right-continuous)."""
    xs = np.atleast_1d(np.asarray(x, dtype=np.float64))
    xmax = float(np.max(xs)) if xs.size else 0.0
    pps = prime_powers(xmax)
    locs = np.array([pp.n for pp in pps], dtype=np.float64)
    cum = np.cumsum([pp.weight for pp in pps]) if pps else np.empty(0)
    idx = np.searchsorted(locs, xs, side="right")
    return np.where(idx > 0, np.concatenate([[0.0], cum])[idx], 0.0)


def taper_weights(n: int, kind: Taper = "none") -> FloatArray:
    """Spectral window over the first ``n`` zeros (index 0 = lowest zero)."""
    if n == 0:
        return np.empty(0)
    k = np.arange(n, dtype=np.float64)
    u = (k + 0.5) / n
    match kind:
        case "none":
            return np.ones(n)
        case "hann":
            return 0.5 * (1.0 + np.cos(np.pi * u))
        case "gauss":
            return np.exp(-0.5 * (2.5 * u) ** 2)
        case "fejer":
            return 1.0 - u
    raise ValueError(f"unknown taper {kind!r}")


def _chunks(n: int, size: int) -> Iterator[slice]:
    for s in range(0, n, size):
        yield slice(s, min(s + size, n))


def zero_contributions(x: ArrayLike, gammas: ArrayLike) -> FloatArray:
    """Matrix ``C[k, j] = -2 x_j^{-1/2} cos(gamma_k ln x_j)``: each zero's term in ψ'(x)."""
    xs = np.asarray(x, dtype=np.float64)
    g = np.asarray(gammas, dtype=np.float64)
    return -2.0 * xs**-0.5 * np.cos(np.outer(g, np.log(xs)))


def spike_density(
    x: ArrayLike,
    gammas: ArrayLike,
    taper: Taper = "none",
    include_trivial: bool = True,
    chunk: int = 65536,
) -> FloatArray:
    """Truncated explicit formula for ψ'(x) using the given zeros (x > 1)."""
    xs = np.asarray(x, dtype=np.float64)
    if np.any(xs <= 1.0):
        raise ValueError("spike_density requires x > 1")
    if chunk <= 0:
        raise ValueError("chunk must be positive")
    g = np.asarray(gammas, dtype=np.float64)
    w = taper_weights(g.size, taper)
    # flat C-ordered buffers: reshape(-1) of a non-C array would silently write into a copy
    flat_x = np.ravel(xs, order="C")
    flat_out = np.empty(flat_x.size, dtype=np.float64)
    for sl in _chunks(flat_x.size, chunk):
        xc = flat_x[sl]
        osc = w @ np.cos(np.outer(g, np.log(xc))) if g.size else np.zeros_like(xc)
        val = 1.0 - 2.0 * xc**-0.5 * osc
        if include_trivial:
            val -= 1.0 / (xc * (xc * xc - 1.0))
        flat_out[sl] = val
    return flat_out.reshape(xs.shape)


def psi_explicit(x: ArrayLike, gammas: ArrayLike, taper: Taper = "none") -> FloatArray:
    """Truncated von Mangoldt formula ψ_0(x) ≈ x − 2 Re Σ x^ρ/ρ − log 2π − ½ log(1 − x^-2)."""
    xs = np.asarray(x, dtype=np.float64)
    if np.any(xs <= 1.0):
        raise ValueError("psi_explicit requires x > 1")
    g = np.asarray(gammas, dtype=np.float64)
    w = taper_weights(g.size, taper)
    rho = 0.5 + 1j * g
    flat = xs.reshape(-1)
    total = np.empty_like(flat)
    for sl in _chunks(flat.size, 16384):
        xc = flat[sl]
        terms = np.exp(np.outer(rho, np.log(xc))) / rho[:, None]
        total[sl] = 2.0 * np.real(w @ terms) if g.size else 0.0
    res = flat - total - np.log(2 * np.pi) - 0.5 * np.log1p(-(flat**-2.0))
    return res.reshape(xs.shape)
