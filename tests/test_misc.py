import numpy as np
import pytest

from zeta_music import synth
from zeta_music.cli import main
from zeta_music.composition import render, write_outputs
from zeta_music.config import Section, load_config
from zeta_music.literal import literal
from zeta_music.midi import freq_to_midi


@pytest.mark.parametrize("freq", [110.0, 196.0, 440.0, 1000.0, 1568.0, 2093.0])
def test_pluck_is_in_tune(freq):
    sr = 44100
    y = synth.pluck(freq, 1.0, sr, np.random.default_rng(0))
    nfft = 16 * y.size
    spec = np.abs(np.fft.rfft(y * np.hanning(y.size), nfft))
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    band = (freqs > 0.85 * freq) & (freqs < 1.15 * freq)
    f0 = freqs[band][np.argmax(spec[band])]
    assert abs(1200 * np.log2(f0 / freq)) < 6  # cents


def _fundamental_t60(y, freq, sr):
    t = np.arange(y.size) / sr
    z = y * np.exp(-2j * np.pi * freq * t)
    blk = int(0.05 * sr)
    env = np.abs(np.array([z[i : i + blk].mean() for i in range(0, y.size - blk, blk)]))
    tt = (np.arange(env.size) + 0.5) * blk / sr
    sel = (tt > 0.2) & (tt < 2.5) & (env > env.max() * 1e-3)
    return -60.0 / np.polyfit(tt[sel], 20 * np.log10(env[sel]), 1)[0]


@pytest.mark.parametrize("freq", [98.0, 392.0, 784.0, 1175.0, 1568.0])
def test_pluck_decay_matches_t60(freq):
    """Regression : loop-filter loss made high notes die early (1568 Hz: 0.33 s for t60=2.5 s)."""
    sr = 44100
    y = synth.pluck(freq, 3.0, sr, np.random.default_rng(1), t60=2.5)
    assert _fundamental_t60(y, freq, sr) == pytest.approx(2.5, rel=0.1)


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


SECTION = 'name="a"\nduration=1\nx_start=2\nx_end=3\nzeros_start=1\nzeros_end=2\n'


@pytest.mark.parametrize(
    ("toml", "match"),
    [
        ('title="t"\n[[sections]]\n' + SECTION + 'sweep="expo"\n', r"sections\[0\] \('a'\).*sweep must be"),
        (
            'title="t"\n[[sections]]\n' + SECTION.replace("duration=1", 'duration="long"'),
            r"sections\[0\].*duration must be",
        ),
        ('title="t"\n[[sections]]\n' + SECTION + "zeros_steps=[3, -1]\n", r"zeros_steps must be a non-negative"),
        ('title="t"\n[[sections]]\n' + SECTION + "loop=0\n", r"loop must be > 0"),
        ('title="t"\n[[sections]]\nname="a"\nduration=1\n', r"missing keys"),
        ('title="t"\nsample_rate=5000\n[[sections]]\n' + SECTION, r"sample_rate must be >= 8000"),
        ('title="t"\ndrone_max_hz=30000\n[[sections]]\n' + SECTION, r"drone_max_hz.*Nyquist"),
        ('title="t"\ntaper="kaiser"\n[[sections]]\n' + SECTION, r"taper must be"),
        ('title="t"\n[[sections]]\n' + SECTION + "[mix]\nreverb_mix=1.5\n", r"\[mix\].*reverb_mix"),
        ('title="t"\n[[sections]]\n' + SECTION + "[mix]\npeak_db=3\n", r"peak_db must be <= 0"),
        ('title="t"\n[[sections]]\n' + SECTION + "[mix]\npluck_db=nan\n", r"pluck_db must be a number or -inf"),
        ("title = \n", r"invalid TOML"),
    ],
)
def test_config_errors_name_the_toml_field(tmp_path, toml, match):
    """review C9: invalid scores fail at load time with the offending TOML location."""
    p = tmp_path / "c.toml"
    p.write_text(toml)
    with pytest.raises(ValueError, match=match):
        load_config(p)


def test_minus_inf_mutes_a_voice(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('title="t"\n[[sections]]\n' + SECTION + "[mix]\npluck_db=-inf\n")
    assert load_config(p).mix.pluck_db == float("-inf")
