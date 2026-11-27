"""Render cache (keys, hits, atomic writes) and parallel plugin rendering."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from zeta_music import cli
from zeta_music import produce as pm
from zeta_music.composition import analyse
from zeta_music.config import CompositionConfig, Section
from zeta_music.produce import FxSpec, Note, Part, RenderCache, RenderError, RenderJob, TempoMap, VoiceSpec

SR, N = 8000, 8000


# Module-level renderers: they must pickle by reference into "spawn" worker processes.
def fake_render(part: Part, voice: VoiceSpec, tuning: str, sr: int, n: int) -> np.ndarray:
    """Deterministic stand-in for a plugin: a decaying tone per note, shaped by the voice's params."""
    out = np.zeros((n, 2), dtype=np.float32)
    t = np.arange(int(0.3 * sr)) / sr
    k = float(voice.params.get("k", 1.0))
    for nt in part.notes:
        f = pm.sine_freq(nt.freq, voice.tuning or tuning, voice.transpose) if nt.freq else 100.0
        tone = (nt.velocity / 127) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * 8)
        a = int(nt.time * sr)
        b = min(a + tone.size, n)
        if a < n:
            out[a:b, 0] += tone[: b - a]
            out[a:b, 1] += 0.5 * tone[: b - a]
    return out


def failing_render(part: Part, voice: VoiceSpec, tuning: str, sr: int, n: int) -> np.ndarray:
    raise ValueError("plugin exploded")


def _voice(name: str = "primes", **kw) -> VoiceSpec:
    kw.setdefault("instrument", "plugin:/fake/Inst.vst3")
    kw.setdefault("load_wait", 0.0)
    return VoiceSpec(name=name, **kw)


def _part(name: str = "primes", shift: float = 0.0) -> Part:
    return Part(name, [Note(0.1 + shift, 0.5, 220.0, 90), Note(0.4, 0.5, 330.0, 70)])


# ----------------------------------------------------------------------------- keys
def test_key_is_stable_and_ignores_mix_settings(tmp_path):
    state = tmp_path / "a.bin"
    state.write_bytes(b"kontakt state")
    v = _voice(state=str(state), params={"a": 1.0, "b": 2.0})
    k = pm.render_key(v, _part(), "tempered", SR, N)
    assert k == pm.render_key(_voice(state=str(state), params={"b": 2.0, "a": 1.0}), _part(), "tempered", SR, N)
    assert len(k) == 64 and int(k, 16) >= 0
    copy = tmp_path / "copy.bin"
    copy.write_bytes(state.read_bytes())
    irrelevant = [
        dataclasses.replace(v, gain_db=-6.0),
        dataclasses.replace(v, send=0.5),
        dataclasses.replace(v, highpass_hz=90.0, lowpass_hz=3000.0, presence_db=2.0),
        dataclasses.replace(v, fx=(FxSpec("pedalboard:Chorus"),)),
        dataclasses.replace(v, state=str(copy)),  # same bytes elsewhere
        dataclasses.replace(v, name="bells"),
    ]
    for w in irrelevant:
        assert pm.render_key(w, _part(), "tempered", SR, N) == k, w
    # a voice forced to tempered renders the same in both tunings: one key
    t = dataclasses.replace(v, tuning="tempered")
    assert pm.render_key(t, _part(), "just", SR, N) == pm.render_key(t, _part(), "tempered", SR, N)


def test_key_changes_with_every_input(tmp_path, monkeypatch):
    state = tmp_path / "a.bin"
    state.write_bytes(b"kontakt state")
    v = _voice(state=str(state), params={"a": 1.0})
    base = pm.render_key(v, _part(), "tempered", SR, N)
    variants = {
        "note time": pm.render_key(v, _part(shift=0.05), "tempered", SR, N),
        "pitch": pm.render_key(
            v, Part("primes", [Note(0.1, 0.5, 247.0, 90), Note(0.4, 0.5, 330.0, 70)]), "tempered", SR, N
        ),
        "velocity": pm.render_key(
            v, Part("primes", [Note(0.1, 0.5, 220.0, 91), Note(0.4, 0.5, 330.0, 70)]), "tempered", SR, N
        ),
        "duration": pm.render_key(
            v, Part("primes", [Note(0.1, 0.6, 220.0, 90), Note(0.4, 0.5, 330.0, 70)]), "tempered", SR, N
        ),
        "tuning": pm.render_key(v, _part(), "just", SR, N),
        "transpose": pm.render_key(dataclasses.replace(v, transpose=12.0), _part(), "tempered", SR, N),
        "sample rate": pm.render_key(v, _part(), "tempered", 16000, N),
        "length": pm.render_key(v, _part(), "tempered", SR, N + 1),
        "plugin": pm.render_key(
            dataclasses.replace(v, instrument="plugin:/fake/Other.vst3"), _part(), "tempered", SR, N
        ),
        "plugin name": pm.render_key(dataclasses.replace(v, plugin_name="X"), _part(), "tempered", SR, N),
        "params": pm.render_key(dataclasses.replace(v, params={"a": 1.5}), _part(), "tempered", SR, N),
        "load_wait": pm.render_key(dataclasses.replace(v, load_wait=12.0), _part(), "tempered", SR, N),
        "program": pm.render_key(dataclasses.replace(v, program=3), _part(), "tempered", SR, N),
        "no state": pm.render_key(dataclasses.replace(v, state=None), _part(), "tempered", SR, N),
    }
    state.write_bytes(b"another sound")
    variants["state bytes"] = pm.render_key(v, _part(), "tempered", SR, N)
    state.write_bytes(b"kontakt state")
    assert pm.render_key(v, _part(), "tempered", SR, N) == base
    monkeypatch.setattr(pm, "CACHE_VERSION", pm.CACHE_VERSION + 1)
    variants["code version"] = pm.render_key(v, _part(), "tempered", SR, N)
    for what, k in variants.items():
        assert k != base, what
    assert len(set(variants.values())) == len(variants)


def test_key_for_soundfont_and_engine_voices(tmp_path):
    sf2 = tmp_path / "a.sf2"
    sf2.write_bytes(b"bank one")
    v = VoiceSpec(name="primes", instrument="sf2", program=0)
    tm = TempoMap.constant(112.5, (5, 4))
    k = pm.render_key(v, _part(), "just", SR, N, soundfont=sf2, tempo=tm)
    assert k == pm.render_key(dataclasses.replace(v, gain_db=3.0), _part(), "just", SR, N, soundfont=sf2, tempo=tm)
    assert k != pm.render_key(dataclasses.replace(v, program=1), _part(), "just", SR, N, soundfont=sf2, tempo=tm)
    assert k != pm.render_key(v, _part(), "just", SR, N, soundfont=sf2, tempo=TempoMap.constant(100.0, (5, 4)))
    sf2.write_bytes(b"bank two")
    assert k != pm.render_key(v, _part(), "just", SR, N, soundfont=sf2, tempo=tm)
    with pytest.raises(FileNotFoundError):
        pm.render_key(v, _part(), "just", SR, N, soundfont=tmp_path / "missing.sf2", tempo=tm)
    z = VoiceSpec(name="zeros", instrument="engine")
    cfg = CompositionConfig("t", [Section("A", 8.0, 1.5, 31.5, 13, 13, loop=8.0)])
    ke = pm.render_key(z, None, "just", SR, N, cfg=cfg)
    assert ke == pm.render_key(dataclasses.replace(z, gain_db=-3.0), None, "tempered", SR, N, cfg=cfg)
    cfg2 = CompositionConfig("t", [Section("A", 8.0, 1.5, 31.5, 13, 21, loop=8.0)])
    assert ke != pm.render_key(z, None, "just", SR, N, cfg=cfg2)


def test_missing_state_file_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="plugin state not found"):
        pm.render_key(_voice(state=str(tmp_path / "nope.bin")), _part(), "tempered", SR, N)


# ----------------------------------------------------------------------------- cache files
def test_atomic_save_never_leaves_partial_files(tmp_path, monkeypatch):
    cache = RenderCache(tmp_path / "c")
    good = np.ones((N, 2), dtype=np.float32)
    cache.store("k", good)
    assert cache.has("k", N) and not cache.has("k", N + 1)

    def broken_save(f, arr, allow_pickle=False):
        f.write(b"\x93NUMPY partial")
        raise OSError("disk full")

    monkeypatch.setattr(pm.np, "save", broken_save)
    with pytest.raises(OSError, match="disk full"):
        cache.store("k", np.zeros((N, 2)))
    with pytest.raises(OSError, match="disk full"):
        cache.store("other", np.zeros((N, 2)))
    monkeypatch.undo()
    assert sorted(p.name for p in cache.root.iterdir()) == ["k.npy"]  # no temp files, no partial entry
    np.testing.assert_array_equal(cache.load("k", N), good)  # the old entry is intact
    # a truncated entry (e.g. copied in by hand) is treated as a miss
    p = cache.path("k")
    p.write_bytes(p.read_bytes()[:-100])
    assert not cache.has("k", N) and cache.load("k", N) is None
    assert pm.clear_cache(cache.root) == 0  # "k" is not a cache key: left alone
    assert pm.clear_cache(tmp_path / "absent") == 0


def test_clear_cache_only_removes_cache_files(tmp_path: Path) -> None:
    root = tmp_path / "out"
    cache = RenderCache(root)
    key = "ab" * 32
    cache.store(key, np.zeros((N, 2)))
    cache.describe(key, {"voices": ["just:x"]})
    (root / f".{key}.npy.x1y2.tmp").write_bytes(b"")
    keep = ["report.json", "mix.npy", "notes.tmp", f"{key}.wav", f"{'ab' * 31}.npy"]
    for name in keep:
        (root / name).write_bytes(b"keep")
    assert pm.clear_cache(root) == 3
    assert sorted(p.name for p in root.iterdir()) == sorted(keep)


def test_key_tracks_plugin_build_and_renderer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = tmp_path / "Synth.vst3" / "Contents"
    bundle.mkdir(parents=True)
    (bundle / "Info.plist").write_text("<string>1.0</string>")
    voice = _voice(instrument=f"plugin:{bundle.parent}")
    part = _part()
    k1 = pm.render_key(voice, part, "just", SR, N)
    (bundle / "Info.plist").write_text("<string>1.1</string>")
    pm._plugin_identity.cache_clear()
    k2 = pm.render_key(voice, part, "just", SR, N)
    assert k1 != k2  # a plugin update in place re-renders
    monkeypatch.setattr(pm, "_version", lambda dist: "999")
    assert pm.render_key(voice, part, "just", SR, N) != k2  # so does a new pedalboard


# ----------------------------------------------------------------------------- parallel
def _jobs(tmp_path: Path, renderer=fake_render) -> list[RenderJob]:
    out = []
    for i, name in enumerate(("primes", "bells", "bass", "pulse")):
        v = _voice(name, params={"k": 1.0 + i / 10})
        part = Part(name, [Note(0.05 * j, 0.2, 110.0 * (1 + i), 60 + j) for j in range(3 + 4 * i)])
        out.append(RenderJob(f"{name}", v, part, "tempered", SR, N, tmp_path / f"{name}.npy", renderer))
    return out


def test_parallel_render_equals_sequential(tmp_path):
    seq, par = tmp_path / "seq", tmp_path / "par"
    local_ran = []
    pm.render_jobs(_jobs(seq), 1, [lambda: local_ran.append("seq")])
    pm.render_jobs(_jobs(par), 3, [lambda: local_ran.append("par")])
    assert local_ran == ["seq", "par"]
    for j in _jobs(seq):
        a, b = np.load(seq / f"{j.key}.npy"), np.load(par / f"{j.key}.npy")
        assert a.shape == (N, 2) and np.any(a)
        np.testing.assert_array_equal(a, b)


def test_worker_failure_names_the_voice(tmp_path):
    jobs = _jobs(tmp_path)
    jobs[2] = dataclasses.replace(jobs[2], renderer=failing_render)
    with pytest.raises(
        RenderError, match=r"voice 'bass' with plugin:/fake/Inst.vst3 failed: ValueError: plugin exploded"
    ):
        pm.render_jobs(jobs, 2)
    with pytest.raises(RenderError, match="plugin exploded"):
        pm.render_jobs(jobs, 1)
    assert not (tmp_path / "bass.npy").exists()


def test_default_jobs(monkeypatch):
    monkeypatch.setattr(pm.os, "cpu_count", lambda: 16)
    assert [pm.default_jobs(k) for k in (0, 1, 3, 5)] == [1, 1, 3, 4]
    monkeypatch.setattr(pm.os, "cpu_count", lambda: 4)
    assert pm.default_jobs(5) == 2


# ----------------------------------------------------------------------------- produce
SCORE = """
title = "mini"
sample_rate = 16000
control_rate = 1000
drone_base_hz = 82.41
pluck_base_hz = 98.0
[[sections]]
name = "A"
duration = 8.0
x_start = 1.5
x_end = 31.5
loop = 8.0
zeros_start = 13
zeros_end = 13
[produce]
tail = 1.0
[produce.voices.primes]
instrument = "plugin:/fake/Inst.vst3"
tuning = "tempered"
load_wait = 0.0
gain_db = {primes_gain}
send = 0.2
[produce.voices.bass]
instrument = "plugin:/fake/Inst.vst3"
load_wait = 0.0
transpose = {bass_transpose}
[produce.voices.sub]
instrument = "builtin:sine"
[produce.arrangement."A"]
primes = 1.0
bass = 1.0
"""


def _score(tmp_path: Path, primes_gain: float = 0.0, bass_transpose: float = 0.0) -> Path:
    p = tmp_path / "mini.toml"
    p.write_text(SCORE.format(primes_gain=primes_gain, bass_transpose=bass_transpose))
    return p


@pytest.fixture
def counting(monkeypatch):
    calls: list[str] = []

    def render(part, voice, tuning, sr, n):
        calls.append(f"{tuning}:{voice.name}")
        return fake_render(part, voice, tuning, sr, n)

    monkeypatch.setattr(pm, "render_plugin", render)
    return calls


def test_cache_hit_skips_rendering(tmp_path, counting):
    pytest.importorskip("pyloudnorm")
    import soundfile as sf

    cache = tmp_path / "cache"
    run = lambda out, **kw: pm.produce(_score(tmp_path, **kw), tmp_path / out, cache_dir=cache, jobs=1)  # noqa: E731
    first = run("a")
    # primes is forced to tempered: one render serves both tunings; bass renders per tuning
    assert sorted(counting) == ["just:bass", "just:primes", "tempered:bass"]
    assert first["render"]["from_cache"] == []
    counting.clear()
    again = run("b")
    assert counting == [] and again["render"]["rendered"] == []
    a, _ = sf.read(first["paths"]["master_just_wav"])
    b, _ = sf.read(again["paths"]["master_just_wav"])
    np.testing.assert_array_equal(a, b)  # cached audio gives the identical master
    run("c", primes_gain=-6.0)  # a mix change renders nothing
    assert counting == []
    changed = run("d", bass_transpose=12.0)  # a change to one voice renders only that voice
    assert sorted(counting) == ["just:bass", "tempered:bass"]
    assert changed["render"]["from_cache"] == ["just:primes", "tempered:primes"]
    counting.clear()
    pm.produce(_score(tmp_path), tmp_path / "e", cache_dir=None, jobs=1)  # no cache: everything again
    assert len(counting) == 3
    assert not list(cache.glob("*.tmp"))


def test_produce_parallel_equals_sequential(tmp_path, monkeypatch):
    pytest.importorskip("pyloudnorm")
    import soundfile as sf

    monkeypatch.setattr(pm, "render_plugin", fake_render)
    score = _score(tmp_path)
    seq = pm.produce(score, tmp_path / "seq", ("tempered",), cache_dir=tmp_path / "c1", jobs=1)
    par = pm.produce(score, tmp_path / "par", ("tempered",), cache_dir=tmp_path / "c2", jobs=2)
    assert par["render"]["workers"] == 2
    a, _ = sf.read(seq["paths"]["master_tempered_wav"])
    b, _ = sf.read(par["paths"]["master_tempered_wav"])
    np.testing.assert_array_equal(a, b)


def test_render_cache_parts_are_real_notes(tmp_path):
    """The mini score's plugin voices have notes (the cache tests above are not vacuous)."""
    cfg, prod = pm.load_score(_score(tmp_path))
    gammas, tl, _s, events = analyse(cfg)
    parts = pm.build_parts(cfg, prod, tl, gammas, events)
    assert parts["primes"].notes and parts["bass"].notes


# ----------------------------------------------------------------------------- CLI
def test_cli_cache_and_jobs_flags(tmp_path, monkeypatch):
    seen = {}

    def fake_produce(score, out, tunings, **kw):
        seen.update(kw)
        return {"title": "t", "notes": {}, "paths": {}, "reports": {}}

    monkeypatch.setattr(pm, "produce", fake_produce)
    cache = tmp_path / "cache"
    assert cli.main(["produce", "x.toml", "--cache-dir", str(cache), "--jobs", "3"]) == 0
    assert seen["cache_dir"] == cache and seen["jobs"] == 3
    assert cli.main(["produce", "x.toml", "--no-cache"]) == 0
    assert seen["cache_dir"] is None and seen["jobs"] is None
    key = "cd" * 32
    RenderCache(cache).store(key, np.zeros((10, 2)))
    (cache / "report.json").write_text("{}")  # not a cache file: both clear paths leave it
    assert cli.main(["produce", "x.toml", "--cache-dir", str(cache), "--clear-cache"]) == 0
    assert [p.name for p in cache.iterdir()] == ["report.json"]
    RenderCache(cache).store(key, np.zeros((10, 2)))
    assert cli.main(["clear-cache", "--cache-dir", str(cache)]) == 0
    assert [p.name for p in cache.iterdir()] == ["report.json"]
    assert cli.main(["produce", "x.toml", "--jobs", "0"]) == 2
