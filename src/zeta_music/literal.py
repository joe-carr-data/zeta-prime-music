r"""Literal sonifications: play the explicit-formula sums directly as waveforms.

``log`` mode
    Substituting ``x = e^{t}`` turns every zero's term ``cos(γ_k ln x)`` into a pure tone
    ``cos(γ_k t)``. Mapping ``t = r·τ`` (τ in seconds) makes zero *k* a sine at
    ``r·γ_k/2π`` Hz: the "chord of the zeros". We pick ``r`` so γ₁ lands on ``base_hz``.

``linear`` mode
    Sweep ``x`` linearly in time at audio rate and play ψ'_N(x) − 1 itself. The prime powers
    become clicks whose rhythm is the irregular rhythm of the primes.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray

from .explicit import spike_density, taper_weights
from .zeros import load_zeros

__all__ = ["literal"]


def literal(
    mode: Literal["log", "linear"] = "log",
    n_zeros: int = 200,
    duration: float = 10.0,
    sr: int = 44100,
    base_hz: float = 110.0,
    x_start: float = 1.5,
    x_end: float = 400.0,
    taper: Literal["none", "hann", "gauss", "fejer"] = "gauss",
) -> NDArray[np.float64]:
    """Return a mono float64 waveform normalised to peak 0.9."""
    if n_zeros < 1:
        raise ValueError("literal needs at least 1 zero")
    if duration <= 0 or sr <= 0:
        raise ValueError("duration and sample rate must be positive")
    g = load_zeros(n_zeros)
    n = int(duration * sr)
    tau = np.arange(n) / sr
    if mode == "log":
        r = 2 * np.pi * base_hz / g[0]
        w = taper_weights(g.size, taper) / np.abs(0.5 + 1j * g)
        y = np.zeros(n)
        for gk, wk in zip(g, w, strict=True):
            y += wk * np.cos(gk * r * tau)
        # slow swell so the chord breathes like a struck bell
        y *= np.exp(-tau / max(duration, 1e-9) * 2.0) * (1 - np.exp(-tau * 30))
    elif mode == "linear":
        x = x_start + (x_end - x_start) * tau / duration
        y = spike_density(x, g, taper) - 1.0
        y = y * x / np.log(x)  # compensate the 1/x spike-height decay
    else:
        raise ValueError(f"unknown mode {mode!r}")
    y -= y.mean()
    peak = float(np.max(np.abs(y))) or 1.0
    return 0.9 * y / peak
