"""Visualiser for produced versions: scores with a [produce] table, arrangement-aware labels, --title."""

import shutil

import pytest

from tests.conftest import ROOT
from zeta_music.config import load_config, load_score_config
from zeta_music.video import VideoSpec, _produced_events, produced_levels, render_video

RADIO_J = ROOT / "compositions" / "commercial" / "critical_strip_radio_kontakt.toml"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_load_score_config_accepts_a_produced_score():
    cfg, produce = load_score_config(RADIO_J)
    assert [s.name for s in cfg.sections][:3] == ["Intro", "Tuning in", "Chorus"]
    assert produce is not None and produce["bpm"] == 112.5 and "primes" in produce["voices"]
    with pytest.raises(ValueError, match="unknown keys"):  # the strict loader still rejects it
        load_config(RADIO_J)


def test_load_score_config_keeps_composition_validation(tmp_path):
    plain = ROOT / "compositions" / "critical_strip.toml"
    cfg, produce = load_score_config(plain)
    assert produce is None and cfg.sections
    bad = tmp_path / "bad.toml"
    bad.write_text("bogus = 1\n" + plain.read_text() + "\n[produce]\nbpm = 100\n")
    with pytest.raises(ValueError, match=r"unknown keys \['bogus'\]"):
        load_score_config(bad)
    bad.write_text("produce = 3\n" + plain.read_text())
    with pytest.raises(ValueError, match=r"\[produce\] must be a table"):
        load_score_config(bad)


def _tiny_produce(b_primes: float = 0.0) -> dict:
    return {
        "voices": {"primes": {"instrument": "sf2"}, "bells": {"instrument": "sf2"}},
        "arrangement": {"b": {"primes": b_primes, "bells": 1.0}, "c": {"primes": 1.0}},
    }


def test_produced_levels_mirror_the_arrangement(tiny_config):
    assert produced_levels(_tiny_produce(), tiny_config) == {
        "a": {"bells": 0.0, "primes": 0.0},  # no arrangement entry: silent
        "b": {"bells": 1.0, "primes": 0.0},
        "c": {"bells": 0.0, "primes": 1.0},
    }
    no_bells = {"voices": {"primes": {}}, "arrangement": {"b": {"primes": 1.0, "bells": 2.0}}}
    assert produced_levels(no_bells, tiny_config)["b"] == {"bells": 0.0, "primes": 1.0}  # no bells voice
    with pytest.raises(ValueError, match="not in the score"):
        produced_levels({"voices": {}, "arrangement": {"zz": {}}}, tiny_config)
    with pytest.raises(ValueError, match="must be a number"):
        produced_levels({"voices": {"primes": {}}, "arrangement": {"b": {"primes": "loud"}}}, tiny_config)


def test_labelled_events_are_the_notes_the_producer_plays(tiny_config):
    """The video labels exactly the primes/bells notes of the produced parts, at the same times."""
    pytest.importorskip("mido")
    from zeta_music.composition import analyse
    from zeta_music.produce import bells_part, primes_part, produce_config_from_dict

    _g, tl, _s, events = analyse(tiny_config)
    counts = []
    for b_primes in (0.0, 1.0):
        raw = _tiny_produce(b_primes)
        prod = produce_config_from_dict(raw, tiny_config, "t")
        notes = primes_part(events, tiny_config, prod).notes + bells_part(events, tiny_config, prod).notes
        labelled = sorted(e.time for e in _produced_events(events, tiny_config, tl, raw))
        assert labelled == sorted(n.time for n in notes)
        counts.append(len(labelled))
    assert counts[0] < counts[1]  # muting section b's primes removes their labels


def test_cli_video_title_option():
    from zeta_music.cli import build_parser

    argv = ["video", str(RADIO_J), "--audio", "a.wav"]
    assert build_parser().parse_args([*argv, "--title", "The Sound of the Primes"]).title == "The Sound of the Primes"
    assert build_parser().parse_args(argv).title is None


def test_captions_wrap_inside_the_frame():
    from zeta_music.video import CAPTION_CHARS, wrap_caption

    hook = "Add the zeros of ζ one by one and hear the primes come into tune"
    lines = wrap_caption(hook, portrait=True).splitlines()
    assert len(lines) > 1 and all(len(line) <= CAPTION_CHARS[True] for line in lines)
    assert " ".join(lines) == hook
    assert wrap_caption(hook, portrait=False) == hook  # one line in landscape


@pytest.fixture
def tiny_wav(tiny_config, tmp_path):
    import soundfile as sf

    from zeta_music.composition import render

    res = render(tiny_config)
    wav = tmp_path / "a.wav"
    sf.write(wav, res.audio, res.sample_rate)
    return wav


@needs_ffmpeg
def test_render_video_with_produce_table_and_title(tiny_config, tiny_wav, tmp_path):
    spec = VideoSpec(fps=5, start=2.0, end=3.0, title="The Sound of the Primes $x$")
    assert render_video(tiny_config, tiny_wav, tmp_path / "p.mp4", spec, produce=_tiny_produce()).exists()
    with pytest.raises(ValueError, match="not in the score"):
        render_video(tiny_config, tiny_wav, tmp_path / "q.mp4", spec, produce={"arrangement": {"zz": {}}})
