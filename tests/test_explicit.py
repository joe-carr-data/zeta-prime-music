import math

import numpy as np
import pytest
from scipy.signal import find_peaks

from zeta_music.explicit import (
    chebyshev_psi,
    prime_powers,
    primes_upto,
    psi_explicit,
    spike_density,
    taper_weights,
    von_mangoldt,
)
from zeta_music.zeros import load_zeros


def test_primes_upto():
    assert primes_upto(30).tolist() == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    assert primes_upto(1).size == 0


@pytest.mark.parametrize(
    ("n", "expected"),
    [(1, 0), (2, math.log(2)), (8, math.log(2)), (9, math.log(3)), (12, 0), (97, math.log(97)), (125, math.log(5))],
)
def test_von_mangoldt(n, expected):
    assert von_mangoldt(n) == pytest.approx(expected)


def test_prime_powers_upto_30():
    assert [pp.n for pp in prime_powers(30)] == [2, 3, 4, 5, 7, 8, 9, 11, 13, 16, 17, 19, 23, 25, 27, 29]


def test_chebyshev_psi_exact():
    # psi(10) = log lcm(1..10) = log 2520
    assert chebyshev_psi(10.0)[0] == pytest.approx(math.log(2520))
    assert chebyshev_psi([1.5])[0] == 0.0


def test_psi_explicit_converges():
    x = np.array([10.5, 20.5, 50.5, 100.5])
    err = np.abs(psi_explicit(x, load_zeros(300), "gauss") - chebyshev_psi(x))
    assert np.all(err < 0.6)


def test_more_zeros_is_better():
    x = np.linspace(2.5, 60.5, 59)
    exact = chebyshev_psi(x)
    errs = [np.mean(np.abs(psi_explicit(x, load_zeros(n)) - exact)) for n in (10, 100, 400)]
    assert errs[0] > errs[1] > errs[2]


def test_spikes_land_on_prime_powers():
    x = np.linspace(1.5, 30.5, 30000)
    y = spike_density(x, load_zeros(200), "gauss")
    peaks, _ = find_peaks(y, prominence=2.0)
    assert np.round(x[peaks]).astype(int).tolist() == [pp.n for pp in prime_powers(30)]
    assert np.max(np.abs(x[peaks] - np.round(x[peaks]))) < 0.05


def test_spike_density_rejects_x_le_1():
    with pytest.raises(ValueError):
        spike_density([1.0], load_zeros(3))


@pytest.mark.parametrize("kind", ["none", "hann", "gauss", "fejer"])
def test_taper_weights(kind):
    w = taper_weights(10, kind)
    assert w.shape == (10,) and np.all(w > 0) and np.all(w <= 1) and np.all(np.diff(w) <= 0)
    with pytest.raises(ValueError):
        taper_weights(3, "bogus")


def test_spike_density_layout_independent():
    """Regression: Fortran-ordered input used to return uninitialised memory."""
    g = load_zeros(20)
    a = np.array([[2.0, 3.0, 4.5], [5.0, 7.0, 9.5]])
    expected = np.array([[spike_density([v], g)[0] for v in row] for row in a])
    for arr in (a, np.asfortranarray(a)):
        np.testing.assert_allclose(spike_density(arr, g), expected, rtol=1e-12)
    # negative strides
    np.testing.assert_allclose(spike_density(a[:, ::-1], g), expected[:, ::-1], rtol=1e-12)
    np.testing.assert_allclose(spike_density(a, g, chunk=1), expected, rtol=1e-12)


@pytest.mark.parametrize("chunk", [0, -1])
def test_spike_density_rejects_bad_chunk(chunk):
    with pytest.raises(ValueError):
        spike_density([2.0], load_zeros(3), chunk=chunk)
