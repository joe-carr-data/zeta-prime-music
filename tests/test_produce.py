"""Pure parts of the production pipeline: tempo map, tuning, MIDI, arrangement, loudness, limiting."""

from __future__ import annotations

import mido
import numpy as np
import pytest

from tests.conftest import ROOT
from zeta_music.composition import analyse
from zeta_music.config import CompositionConfig, Section
from zeta_music.produce import (
    Note,
    Part,
    ProduceConfig,
    SectionArrangement,
    TempoMap,
    VoiceSpec,
    _allocate,
    build_parts,
    compress,
    grid_bpm,
    high_shelf,
    limit,
    load_score,
    lufs_gain_db,
    note_for,
    part_messages,
    produce_config_from_dict,
    pulse_part,
    true_peak_db,
    write_midi_file,
)

SCORE = ROOT / "compositions" / "commercial" / "critical_strip_radio.toml"


# ----------------------------------------------------------------------------- tempo
def test_grid_bpm_puts_integers_on_sixteenths():
    assert grid_bpm(8.0, 30) == pytest.approx(112.5)
    assert grid_bpm(8.0, 30, sixteenths_per_integer=4) == pytest.approx(225.0)


def test_tempo_map_bar_and_cycle():
    tm = TempoMap.constant(112.5, (5, 4))
    assert tm.bar_ticks == 5 * 960
    bar_s = tm.seconds(tm.bar_ticks)
    assert bar_s == pytest.approx(8.0 / 3.0)
    assert tm.ticks(8.0) == pytest.approx(3 * tm.bar_ticks)  # one 8 s cycle = three bars of 5/4
    assert tm.seconds(tm.grid_ticks(16)) == pytest.approx(1 / 7.5)


def test_tempo_map_piecewise_roundtrip():
    tm = TempoMap(((0.0, 120.0), (10.0, 60.0)), (4, 4), 480)
    assert tm.ticks(10.0) == pytest.approx(10 * 2 * 480)
    assert tm.ticks(12.0) == pytest.approx(10 * 2 * 480 + 2 * 480)
    for t in (0.0, 3.3, 10.0, 17.25):
        assert tm.seconds(tm.ticks(t)) == pytest.approx(t)
    with pytest.raises(ValueError):
        TempoMap(((1.0, 120.0),))
    with pytest.raises(ValueError):
        TempoMap(((0.0, 120.0), (0.0, 90.0)))


def test_quantiser_snaps_to_grid():
    tm = TempoMap.constant(112.5, (5, 4))
    q = tm.quantiser(16)
    s16 = 1 / 7.5
    assert q(3 * s16 + 0.02) == pytest.approx(3 * s16)
    assert q(5 * s16 - 0.05) == pytest.approx(5 * s16)


# ----------------------------------------------------------------------------- tuning
def test_note_for_tempered_and_just():
    assert note_for(98.0, "tempered") == (43, 0)  # G2
    assert note_for(41.2, "tempered") == (28, 0)  # E1
    note, bend = note_for(98.0 * 7 / 4 * 2, "just")  # harmonic 7th, F4 -31 cents
    assert note == 65
    assert bend == pytest.approx(-0.31 / 2 * 8192, abs=60)
    assert note_for(98.0 * 7 / 4 * 2, "tempered") == (65, 0)
    with pytest.raises(ValueError):
        note_for(100.0, "pythagorean")


def test_allocate_single_channel_cuts_only_repeated_keys():
    alloc = _allocate([(0.0, 2.0, 60), (0.5, 2.0, 64), (1.0, 3.0, 60)], [3])
    assert [a[0] for a in alloc] == [3, 3, 3]
    assert alloc[0][2] == 1.0  # the earlier 60 ends when 60 is struck again
    assert alloc[1][2] == 2.0  # a different key rings on


def test_allocate_many_channels_gives_private_channels():
    notes = [(i * 0.1, i * 0.1 + 1.0, 60 + i) for i in range(5)]
    alloc = _allocate(notes, [0, 1, 2, 3, 4, 5])
    assert len({a[0] for a in alloc}) == 5


def _voice(name="primes", **kw):
    kw.setdefault("instrument", "sf2")
    return VoiceSpec(name=name, **kw)


def test_midi_files_just_vs_tempered(tmp_path):
    tm = TempoMap.constant(112.5, (5, 4))
    part = Part("primes", [Note(0.1333, 2.0, 98.0 * 7 / 4, 100, 0.3), Note(0.4, 2.0, 98.0 * 11 / 8, 90, -0.2)])
    drums = Part("pulse", [Note(0.0, 0.2, 0.0, 70, key=36)], drums=True)
    parts = [(_voice(program=24), part), (_voice("pulse", program=40), drums)]
    just = write_midi_file(tmp_path / "j.mid", "t", parts, tm, "just", [(0.0, "Intro")])
    temp = write_midi_file(tmp_path / "t.mid", "t", parts, tm, "tempered", [(0.0, "Intro")])
    mj, mt = mido.MidiFile(just), mido.MidiFile(temp)
    assert mj.type == 1 and len(mj.tracks) == 3
    head = list(mj.tracks[0])
    assert any(m.type == "set_tempo" and m.tempo == mido.bpm2tempo(112.5) for m in head)
    assert any(m.type == "time_signature" and (m.numerator, m.denominator) == (5, 4) for m in head)
    assert any(m.type == "marker" and m.text == "Intro" for m in head)
    bends_j = [m.pitch for m in mj.tracks[1] if m.type == "pitchwheel"]
    assert any(b != 0 for b in bends_j)
    assert not any(m.type == "pitchwheel" for t in mt.tracks for m in t)
    on_ch_j = {m.channel for m in mj.tracks[1] if m.type == "note_on"}
    on_ch_t = {m.channel for m in mt.tracks[1] if m.type == "note_on"}
    assert len(on_ch_j) == 2 and len(on_ch_t) == 1  # just: a channel per sounding note
    assert {m.channel for t in (mj.tracks[2], mt.tracks[2]) for m in t if m.type == "note_on"} == {9}


def test_quantised_midi_onsets_on_grid(tmp_path):
    tm = TempoMap.constant(112.5, (5, 4))
    part = Part("primes", [Note(t, 0.5, 220.0, 90) for t in (0.14, 0.41, 0.69, 1.07)])
    p = write_midi_file(tmp_path / "q.mid", "t", [(_voice(), part)], tm, "tempered", quantise=16)
    tick, ons = 0, []
    for m in mido.MidiFile(p).tracks[1]:
        tick += m.time
        if m.type == "note_on":
            ons.append(tick)
    assert ons and all(t % 240 == 0 for t in ons)


def test_part_messages_just_sets_bend_range():
    msgs = part_messages(Part("primes", [Note(0.0, 1.0, 100.0, 80)]), _voice(), "just", [0, 1])
    rpn = [(m.control, m.value) for _, _, m in msgs if m.type == "control_change" and m.channel == 0]
    assert (101, 0) in rpn and (100, 0) in rpn and (6, 2) in rpn


# ----------------------------------------------------------------------------- score
def test_radio_score_loads_and_is_on_the_grid():
    cfg, prod = load_score(SCORE)
    bar = 60 / prod.bpm * 4 / prod.meter[1] * prod.meter[0]
    for s in cfg.sections:  # every section is a whole number of bars
        assert s.duration / bar == pytest.approx(round(s.duration / bar))
    for s in cfg.sections:
        if s.loop:
            assert grid_bpm(s.loop, abs(s.x_end - s.x_start)) == pytest.approx(prod.bpm)
    assert 160 <= cfg.duration + prod.tail <= 200  # about three minutes


def test_score_validation_errors():
    cfg = CompositionConfig("t", [Section("A", 8.0, 1.5, 31.5, 1, 1, loop=8.0)])
    ok = {"voices": {"primes": {"instrument": "sf2"}}}
    assert isinstance(produce_config_from_dict(ok, cfg, "x"), ProduceConfig)
    with pytest.raises(ValueError, match="unknown voice"):
        produce_config_from_dict({"voices": {"kazoo": {"instrument": "sf2"}}}, cfg, "x")
    with pytest.raises(ValueError, match="not in the score"):
        produce_config_from_dict(ok | {"arrangement": {"B": {"primes": 1.0}}}, cfg, "x")
    with pytest.raises(ValueError, match="unknown keys"):
        produce_config_from_dict(ok | {"tempo": 3}, cfg, "x")
    with pytest.raises(ValueError, match="pulse"):
        produce_config_from_dict(ok | {"arrangement": {"A": {"pulse": "techno"}}}, cfg, "x")
    with pytest.raises(ValueError, match="instrument"):
        produce_config_from_dict({"voices": {"primes": {"instrument": "kontakt"}}}, cfg, "x")
    fx = {
        "voices": {
            "primes": {"instrument": "plugin:/x.vst3", "state": "s.bin", "fx": [{"plugin": "pedalboard:Chorus"}]}
        }
    }
    v = produce_config_from_dict(fx, cfg, "x").voices["primes"]
    assert v.kind == "plugin" and v.target == "/x.vst3" and v.fx[0].plugin == "pedalboard:Chorus"


def test_pulse_never_lands_on_an_integer():
    """With the grid tempo, integers sit on odd sixteenths and the pulse only on even ones."""
    cfg = CompositionConfig("t", [Section("A", 16.0, 1.5, 31.5, 34, 34, loop=8.0)], control_rate=1000)
    prod = ProduceConfig(
        {"pulse": _voice("pulse")}, {"A": SectionArrangement({}, pulse="groove")}, bpm=112.5, meter=(5, 4)
    )
    pulse = pulse_part(cfg, prod)
    s16 = 1 / 7.5
    pos = np.array([n.time / s16 for n in pulse.notes])
    assert pulse.notes and np.allclose(pos, np.round(pos)) and np.all(np.round(pos) % 2 == 0)
    _, _tl, _, events = analyse(cfg)
    primes = np.array([e.time for e in events if e.kind != "ghost"])
    gap = np.min(np.abs(primes[:, None] - np.array([n.time for n in pulse.notes])[None, :]))
    assert gap > 0.4 * s16  # never within less than half a sixteenth of a prime


def test_build_parts_from_engine():
    cfg = CompositionConfig(
        "t",
        [Section("Intro", 8.0, 1.2, 3.2, 0, 1, pluck_gain=0.0), Section("A", 16.0, 1.5, 31.5, 1, 34, loop=8.0)],
        control_rate=1000,
    )
    voices = {k: _voice(k) for k in ("primes", "bells", "drone", "bass", "sub", "pulse")}
    arr = {
        "Intro": SectionArrangement({"drone": 1.0}),
        "A": SectionArrangement({"primes": 1.0, "bells": 1.0, "drone": 1.0, "bass": 1.0}, "drive", "bar"),
    }
    prod = ProduceConfig(voices, arr)
    gammas, tl, _, events = analyse(cfg)
    parts = build_parts(cfg, prod, tl, gammas, events)
    assert len(parts["primes"].notes) == sum(e.kind != "prime_power" for e in events)
    assert all(n.time >= 8.0 for n in parts["primes"].notes)  # intro has no plucks
    first = min(parts["drone"].notes, key=lambda n: n.time)
    assert first.freq == pytest.approx(cfg.drone_base_hz) and first.time < 8.0  # zero 1 enters in the intro
    assert parts["drone"].controls[0].value == 0  # ... from silence (no zeros yet)
    assert max(n.freq for n in parts["drone"].notes) == pytest.approx(cfg.drone_base_hz * gammas[7] / gammas[0])
    assert all(n.freq < 60 for n in parts["sub"].notes)
    assert parts["bass"].notes and all(n.time >= 8.0 for n in parts["bass"].notes)


# ----------------------------------------------------------------------------- loudness & dynamics
def test_lufs_gain():
    assert lufs_gain_db(-20.0, -14.0) == pytest.approx(6.0)
    assert lufs_gain_db(-9.5, -14.0) == pytest.approx(-4.5)
    assert lufs_gain_db(float("-inf"), -14.0) == 0.0


def test_lufs_gain_reaches_target():
    pyln = pytest.importorskip("pyloudnorm")
    sr = 44100
    t = np.arange(5 * sr) / sr
    x = 0.05 * np.stack([np.sin(2 * np.pi * 997 * t)] * 2, axis=1)
    meter = pyln.Meter(sr)
    g = lufs_gain_db(meter.integrated_loudness(x), -14.0)
    assert meter.integrated_loudness(x * 10 ** (g / 20)) == pytest.approx(-14.0, abs=0.05)


def test_true_peak_sees_intersample_peaks():
    sr = 44100
    n = np.arange(4096)
    x = np.sin(2 * np.pi * (sr / 4) * n / sr + np.pi / 4)  # samples at +-0.707, true peak 1.0
    stereo = np.stack([x, x], axis=1)
    assert 20 * np.log10(np.max(np.abs(stereo))) == pytest.approx(-3.0, abs=0.1)
    assert true_peak_db(stereo) == pytest.approx(0.0, abs=0.3)


def test_limiter_holds_ceiling_and_leaves_quiet_audio_alone():
    sr = 44100
    rng = np.random.default_rng(0)
    loud = rng.standard_normal((sr * 2, 2)) * 0.5
    y = limit(loud, sr, ceiling_db=-1.0)
    assert true_peak_db(y) <= -0.9
    quiet = loud * 0.05
    assert np.allclose(limit(quiet, sr, ceiling_db=-1.0), quiet)


def test_high_shelf_gain():
    sr = 44100
    t = np.arange(sr) / sr
    for f, expect in ((100.0, 0.0), (15000.0, 4.0)):
        x = np.sin(2 * np.pi * f * t)[:, None]
        y = high_shelf(x, sr, 3500.0, 4.0)
        mid = slice(sr // 4, 3 * sr // 4)
        gain = 20 * np.log10(np.std(y[mid]) / np.std(x[mid]))
        assert gain == pytest.approx(expect, abs=0.3)


def test_compressor_unity_below_threshold():
    sr = 44100
    t = np.arange(sr) / sr
    x = 0.01 * np.stack([np.sin(2 * np.pi * 220 * t)] * 2, axis=1)
    y, stats = compress(x, sr, threshold_db=-16.0, ratio=2.0)
    assert np.allclose(y, x) and stats["max_gr_db"] == 0.0
    _y2, stats2 = compress(x * 50, sr, threshold_db=-16.0, ratio=2.0)
    assert stats2["max_gr_db"] > 1.0
