"""zeta-music: composing with the nontrivial zeros of the Riemann zeta function."""

from .explicit import chebyshev_psi, prime_powers, psi_explicit, spike_density
from .zeros import load_zeros

__all__ = ["__version__", "chebyshev_psi", "load_zeros", "prime_powers", "psi_explicit", "spike_density"]
try:  # single source of truth: the version in pyproject.toml, via the installed metadata
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("zeta-music")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0+unknown"
