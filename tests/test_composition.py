import numpy as np
import pytest

from zeta_music.composition import (
    build_timeline,
    detect_events,
    event_pan,
    event_pitch,
    fold,
    render,
    salience_curve,
)
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


def test_pitch_is_continuous_across_powers_of_two():
    """Regression : x=1.9998 and x=2.0005 must not be an octave apart."""
    lo, hi = event_pitch(1.9998, 98.0), event_pitch(2.0005, 98.0)
    assert abs(1200 * np.log2(hi / lo)) < 1.0  # cents
    for n in (4, 8, 16, 32):
        a, b = event_pitch(n - 0.01, 98.0), event_pitch(n + 0.01, 98.0)
        # the only difference left is the honest detune x/n, never an octave
        assert 1200 * np.log2(b / a) == pytest.approx(1200 * np.log2((n + 0.01) / (n - 0.01)), abs=0.01)


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


def test_salience_is_bounded_while_first_zero_fades_in():
    """Regression : N -> 0 used to give -3.9e10 at x = 1.2."""
    g = load_zeros(5)
    x = np.full(5, 1.2)
    n = np.array([0.0, 1e-6, 0.1, 0.5, 1.0])
    s = salience_curve(x, n, g)
    assert s[0] == 0.0
    assert np.all(np.isfinite(s)) and np.max(np.abs(s)) < 10
    # fades in proportionally to presence while N < 1
    np.testing.assert_allclose(s[1:4] / s[4], n[1:4], rtol=1e-9)


@pytest.mark.parametrize("taper", ["none", "gauss", "hann", "fejer"])
def test_salience_full_scale_at_one_zero(taper):
    """At N=1 the floor must not attenuate: S equals the unfloored normalisation."""
    g = load_zeros(3)
    x = np.array([2.0, 3.0, 5.0])
    s = salience_curve(x, np.ones(3), g, taper)
    unfloored = (
        -2.0 * x**-0.5 * np.cos(g[0] * np.log(x)) * x / np.log(x) * np.pi / (2 * np.pi / np.log(g[0] / (2 * np.pi)))
    )
    np.testing.assert_allclose(s, unfloored, rtol=1e-9)


def test_pan_is_continuous_across_powers_of_two():
    """Regression : stereo position must not flip as a peak converges on n."""
    for n in (2, 4, 8, 16):
        assert event_pan(n - 0.01) == event_pan(n + 0.01) == event_pan(float(n))


def test_segments_mark_sections_and_loops(tiny_config):
    tl = build_timeline(tiny_config)
    # a: one sweep; b: 2 loops; c: one sweep that starts where b ended (x=20 -> 20, no jump back)
    assert np.unique(tl.segment).tolist() == [0, 1, 2, 3]
    assert tl.segment[np.searchsorted(tl.t, 6.0)] == 3


def test_descending_sweep_finds_primes():
    """Regression : a sweep running down the number line used to lose every note."""
    from zeta_music.config import CompositionConfig, Section

    cfg = CompositionConfig(
        title="down", sample_rate=8000, control_rate=1000, drone_max_hz=3000.0,
        sections=[Section("down", 6.0, 30.0, 1.6, 150, 150)],
    )  # fmt: skip
    tl = build_timeline(cfg)
    sal = salience_curve(tl.x, tl.n_zeros, load_zeros(150))
    primes = [e.nearest for e in detect_events(tl, sal, cfg) if e.kind == "prime"]
    assert primes == [29, 23, 19, 17, 13, 11, 7, 5, 3, 2]


def test_note_level_follows_salience(tiny_config):
    """Regression : a p^2 bell must be half the level of a prime pluck at equal mix gain."""
    from zeta_music.composition import Event, _render_notes

    tl = build_timeline(tiny_config)
    sr = tiny_config.sample_rate
    evs = [
        Event(4.0, 5.0, 1.0, 5, "prime", 50.0, 245.0, 0.0),  # away from the gain ramp at t=2
        Event(5.0, 9.0, 0.5, 9, "prime_power", 50.0, 220.0, 0.0),
    ]
    plucks, bells = _render_notes(tiny_config, tl, evs, int(8 * sr))
    pan0 = np.cos(np.pi / 4)
    assert np.max(np.abs(plucks)) == pytest.approx(1.0 * pan0, rel=2e-3)
    assert np.max(np.abs(bells)) == pytest.approx(0.5 * pan0, rel=2e-3)


def test_muted_section_never_sounds():
    """Regression : the smoothed gain rises before an unmute and leaked notes into a muted section."""
    from zeta_music.composition import analyse
    from zeta_music.config import CompositionConfig, Section

    cfg = CompositionConfig(
        title="mute", sample_rate=8000, control_rate=1000, drone_max_hz=3000.0,
        sections=[
            Section("muted", 1.0, 1.5, 31.5, 50, 50, pluck_gain=0.0),
            Section("open", 1.0, 1.5, 31.5, 50, 50),
        ],
    )  # fmt: skip
    _, _, _, events = analyse(cfg)
    assert events, "the unmuted bar must still sound"
    assert all(e.time >= 1.0 for e in events)


@pytest.mark.parametrize("loop", [0.1, 0.3, 0.7, 1.1])
def test_decimal_loops_wrap_exactly_at_segment_boundaries(loop):
    """Regression : floor(u/loop) and mod(u, loop) disagreed, putting the wrap inside a bar."""
    from zeta_music.config import CompositionConfig, Section

    cfg = CompositionConfig(
        title="dec", control_rate=1000,
        sections=[Section("s", round(loop * 10, 6), 1.5, 31.5, 5, 5, loop=loop)],
    )  # fmt: skip
    tl = build_timeline(cfg)
    wraps = np.flatnonzero(np.diff(tl.x) < 0) + 1
    seg_changes = np.flatnonzero(np.diff(tl.segment) != 0) + 1
    np.testing.assert_array_equal(wraps, seg_changes)
    # within every bar x is monotonic
    for a, b in zip([0, *seg_changes], [*seg_changes, tl.x.size], strict=True):
        assert np.all(np.diff(tl.x[a:b]) > 0)


def test_mix_notes_keeps_salience_and_mutes_cleanly():
    """Regression : stem normalisation at the mix stage erased 1/k; -inf dB made NaNs."""
    from zeta_music.composition import mix_notes

    plucks = np.zeros((100, 2))
    bells = np.zeros((100, 2))
    plucks[10] = 1.0  # a unit-salience prime
    bells[50] = 0.5  # a p^2 bell, salience 1/2
    out = mix_notes(plucks, bells, pluck_db=-6.0, bell_db=-6.0)
    assert out[50, 0] / out[10, 0] == pytest.approx(0.5)  # 1/k survives the mix
    bell_only = mix_notes(np.zeros_like(plucks), bells, pluck_db=-6.0, bell_db=-12.0)
    assert np.max(np.abs(bell_only)) == pytest.approx(0.5 * 10 ** (-12 / 20))  # bell_db honoured, not re-normalised
    muted = mix_notes(plucks, bells, pluck_db=float("-inf"), bell_db=-6.0)
    assert np.all(np.isfinite(muted)) and muted[10, 0] == 0.0


def test_quiet_section_is_not_muted():
    """Regression : pluck_gain=0.01 was treated as muted."""
    from zeta_music.composition import analyse
    from zeta_music.config import CompositionConfig, Section

    cfg = CompositionConfig(
        title="quiet", sample_rate=8000, control_rate=1000, drone_max_hz=3000.0,
        sections=[Section("quiet", 2.0, 1.5, 31.5, 50, 50, pluck_gain=0.01)],
    )  # fmt: skip
    assert analyse(cfg)[3], "a quiet (not muted) section must still produce events"


def test_mix_notes_inplace_matches_copy():
    from zeta_music.composition import mix_notes

    rng = np.random.default_rng(0)
    p, b = rng.standard_normal((50, 2)), rng.standard_normal((50, 2))
    expected = mix_notes(p, b, -6.0, -10.0)
    out = np.zeros_like(p)
    mix_notes(p.copy(), b.copy(), -6.0, -10.0, out=out)
    np.testing.assert_allclose(out, expected)
