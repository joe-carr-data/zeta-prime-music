import numpy as np
import pytest

from zeta_music.composition import build_timeline, detect_events, event_pitch, fold, render, salience_curve
from zeta_music.config import load_config
from zeta_music.zeros import load_zeros

from .conftest import ROOT


def test_timeline_shape(tiny_config):
    tl = build_timeline(tiny_config)
    assert tl.t.size == int(tiny_config.duration * tl.rate)
    assert np.all(tl.x > 1)
    # x jumps back at a->b and at b's loop point
    assert np.sum(np.diff(tl.x) < 0) == 2
    assert set(np.unique(tl.n_zeros[(tl.t >= 2) & (tl.t < 4)])) == {5.0}


def test_salience_normalisation():
    """S(n) ~ Lambda(n)/log n: ~1 at primes and ~1/2 at prime squares."""
    g = load_zeros(300)
    xs = np.array([5.0, 7.0, 11.0, 13.0, 9.0, 25.0])
    s = salience_curve(xs, np.full(xs.size, 300.0), g)
    assert np.all((s[:4] > 0.75) & (s[:4] < 1.35))
    assert np.all((s[4:] > 0.35) & (s[4:] < 0.7))


def test_detect_events_converge_with_more_zeros(tiny_config):
    tl = build_timeline(tiny_config)
    sal = salience_curve(tl.x, tl.n_zeros, load_zeros(tiny_config.max_zeros))
    events = detect_events(tl, sal, tiny_config)
    late = [e for e in events if 4.0 <= e.time < 6.0]  # 50 zeros over 1.5..20
    assert {e.nearest for e in late if e.kind == "prime"} >= {2, 3, 5, 7, 11, 13, 17, 19}
    assert all(e.kind != "ghost" for e in late)


def test_fold_and_pitch():
    assert fold(3.0) == pytest.approx(1.5)  # perfect fifth
    assert fold(5.0) == pytest.approx(1.25)  # major third
    assert fold(8.0) == pytest.approx(1.0)
    assert event_pitch(2.0, 100.0) == pytest.approx(100.0)


def test_render_tiny_is_deterministic(tiny_config):
    a = render(tiny_config)
    b = render(tiny_config)
    assert a.audio.shape[1] == 2
    assert np.all(np.isfinite(a.audio))
    assert np.max(np.abs(a.audio)) <= 1.0
    np.testing.assert_array_equal(a.audio, b.audio)
    assert all(e.time >= 2.0 for e in a.events)  # pluck_gain = 0 in section a


def test_shipped_score_parses():
    cfg = load_config(ROOT / "compositions" / "critical_strip.toml")
    assert cfg.max_zeros == 500
    assert cfg.duration > 120
