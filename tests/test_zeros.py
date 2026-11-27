import numpy as np
import pytest

from zeta_music.zeros import BUNDLED_COUNT, compute_zeros, load_zeros

# Odlyzko's tables
KNOWN = [14.134725141734693790, 21.022039638771554993, 25.010857580145688763, 30.424876125859513210]


def test_first_zeros_match_reference():
    np.testing.assert_allclose(load_zeros(4), KNOWN, rtol=0, atol=1e-12)


def test_bundled_count_and_order():
    g = load_zeros(BUNDLED_COUNT)
    assert g.size == BUNDLED_COUNT
    assert np.all(np.diff(g) > 0)
    assert g[-1] == pytest.approx(811.184358847, abs=1e-6)


def test_compute_matches_bundled():
    np.testing.assert_allclose(compute_zeros(99, 101), load_zeros(100)[98:100], atol=1e-9)


def test_load_zero_and_negative():
    assert load_zeros(0).size == 0
    with pytest.raises(ValueError):
        load_zeros(-1)


def test_load_beyond_bundle_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ZETA_MUSIC_CACHE", str(tmp_path))
    g = load_zeros(BUNDLED_COUNT + 2)
    assert g.size == BUNDLED_COUNT + 2 and np.all(np.diff(g) > 0)
    assert (tmp_path / "zeros_extra.npy").exists()
