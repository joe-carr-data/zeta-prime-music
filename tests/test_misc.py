import numpy as np
import pytest

from zeta_music import synth
from zeta_music.cli import main
from zeta_music.composition import render, write_outputs
from zeta_music.config import Section, load_config
from zeta_music.literal import literal
from zeta_music.midi import freq_to_midi


@pytest.mark.parametrize("freq", [110.0, 196.0, 440.0, 1000.0])
def test_pluck_is_in_tune(freq):
    sr = 44100
    y = synth.pluck(freq, 1.0, sr, np.random.default_rng(0))
    nfft = 16 * y.size
    spec = np.abs(np.fft.rfft(y * np.hanning(y.size), nfft))
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    band = (freqs > 0.85 * freq) & (freqs < 1.15 * freq)
    f0 = freqs[band][np.argmax(spec[band])]
    assert abs(1200 * np.log2(f0 / freq)) < 6  # cents


def test_master_peak():
    x = np.random.default_rng(0).standard_normal((44100, 2))
    y = synth.master(x, 44100, peak_db=-1.0)
    assert np.max(np.abs(y)) == pytest.approx(10 ** (-1 / 20), rel=1e-6)


def test_freq_to_midi():
    assert freq_to_midi(440.0) == (69, 0)
    note, bend = freq_to_midi(440.0 * 2 ** (0.5 / 12))
    assert note in (69, 70) and abs(bend) == pytest.approx(2048, abs=2)


@pytest.mark.parametrize("mode", ["log", "linear"])
def test_literal(mode):
    y = literal(mode, n_zeros=20, duration=0.5, sr=8000)
    assert y.shape == (4000,) and np.isfinite(y).all() and np.max(np.abs(y)) == pytest.approx(0.9)


def test_section_validation():
    with pytest.raises(ValueError):
        Section("bad", 1.0, 1.0, 5.0, 1, 2)
    with pytest.raises(ValueError):
        Section("bad", 0.0, 2.0, 5.0, 1, 2)


def test_config_rejects_unknown_keys(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(
        'title="t"\nbogus=1\n[[sections]]\nname="a"\nduration=1\nx_start=2\nx_end=3\nzeros_start=1\nzeros_end=2\n'
    )
    with pytest.raises(ValueError, match="bogus"):
        load_config(p)


def test_write_outputs(tiny_config, tmp_path):
    import mido
    import soundfile as sf

    res = render(tiny_config)
    paths = write_outputs(res, tiny_config, tmp_path, "tiny")
    info = sf.info(paths["wav"])
    assert info.samplerate == 8000 and info.channels == 2 and info.subtype == "PCM_24"
    notes = [m for m in mido.MidiFile(paths["midi"]) if m.type == "note_on"]
    assert len(notes) == len(res.events)


def test_cli_zeros(capsys):
    assert main(["zeros", "2"]) == 0
    assert "14.134725141" in capsys.readouterr().out


def test_cli_bad_config(capsys):
    assert main(["render", "does-not-exist.toml"]) == 2
