"""Figures reproducing the video's visual argument (requires the ``plot`` extra)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .explicit import chebyshev_psi, prime_powers, psi_explicit, spike_density
from .zeros import load_zeros

if TYPE_CHECKING:
    from .composition import RenderResult

__all__ = ["plot_explainer", "plot_score"]


def _plt():  # type: ignore[no-untyped-def]
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_explainer(out: Path, n_zeros: int = 200, xmax: float = 30.0) -> Path:
    """Four panels: single-zero oscillations, the sum of N zeros, and ψ(x) reconstruction."""
    plt = _plt()
    g = load_zeros(n_zeros)
    x = np.linspace(1.05, xmax, 12000)
    fig, ax = plt.subplots(4, 1, figsize=(11, 13), constrained_layout=True)

    for k, c in ((0, "C0"), (1, "C1")):
        ax[0].plot(x, np.cos(g[k] * np.log(x)), c, lw=1, label=f"cos(γ{k + 1} ln x), γ{k + 1}={g[k]:.4f}")
    ax[0].set_title("Each zero is a wave whose wavelength stretches like ln x")
    ax[0].legend(loc="upper right")

    for n, a in ((10, 0.5), (50, 0.7), (n_zeros, 1.0)):
        ax[1].plot(x, spike_density(x, g[:n], "gauss"), lw=0.8, alpha=a, label=f"{n} zeros")
    for pp in prime_powers(xmax):
        ax[1].axvline(pp.n, color="k" if pp.is_prime else "0.6", lw=0.5, ls=":")
    ax[1].set_ylim(-10, 32)
    ax[1].set_title("Adding zeros: spikes appear at primes (dotted black) and prime powers (grey)")
    ax[1].legend(loc="upper right")

    ax[2].plot(x, spike_density(x, g, "none"), lw=0.6, color="C3")
    ax[2].set_ylim(-20, 60)
    ax[2].set_title(f"Untapered sum of {n_zeros} zeros (as in the video): Gibbs ringing between spikes")

    ax[3].step(x, chebyshev_psi(x), where="post", color="k", lw=1, label="ψ(x) exact")
    ax[3].plot(x, psi_explicit(x, g, "gauss"), color="C2", lw=1, label=f"explicit formula, {n_zeros} zeros")
    ax[3].set_title("Chebyshev ψ(x) recovered from the zeros")
    ax[3].legend(loc="upper left")
    for a in ax:
        a.set_xlim(1, xmax)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_score(result: RenderResult, out: Path) -> Path:
    """A 'graphic score': x(τ), active zeros and the detected note events."""
    plt = _plt()
    tl = result.timeline
    fig, ax = plt.subplots(3, 1, figsize=(14, 9), sharex=True, constrained_layout=True)
    ax[0].plot(tl.t, tl.x, lw=0.8, color="k")
    ax[0].set_ylabel("x (number line)")
    ax[0].set_yscale("log")
    colors = {"prime": "C3", "prime_power": "C0", "ghost": "0.7"}
    for kind, c in colors.items():
        ev = [e for e in result.events if e.kind == kind]
        ax[0].scatter([e.time for e in ev], [e.x for e in ev], s=8, c=c, label=kind, zorder=3)
        ax[2].scatter([e.time for e in ev], [e.freq for e in ev], s=[4 + 20 * e.salience for e in ev], c=c, label=kind)
    ax[0].legend(loc="upper left")
    ax[1].plot(tl.t, tl.n_zeros, color="C2")
    ax[1].set_ylabel("active zeros N")
    ax[1].set_yscale("log")
    ax[2].set_ylabel("pitch (Hz)")
    ax[2].set_yscale("log")
    ax[2].set_xlabel("time (s)")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out
