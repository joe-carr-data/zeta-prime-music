import shutil

import numpy as np
import pytest

from zeta_music.video import VideoSpec, _segments, _window, render_video


def test_segments_increment_on_loop_reset():
    x = np.array([1.5, 2.0, 3.0, 1.5, 2.0, 1.5])
    assert _segments(x).tolist() == [0, 0, 0, 1, 1, 2]


def test_window_loop_and_sliding(tiny_config):
    assert _window(tiny_config, 1, 5.0) == (1.5, 20.0)  # loop section: whole bar
    lo, hi = _window(tiny_config, 2, 30.0)  # 20..40 span <= 40: whole range
    assert (lo, hi) == (20.0, 40.0)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_video_smoke(tiny_config, tmp_path):
    import soundfile as sf

    from zeta_music.composition import render

    res = render(tiny_config)
    wav = tmp_path / "a.wav"
    sf.write(wav, res.audio, res.sample_rate)
    out = render_video(tiny_config, wav, tmp_path / "v.mp4", VideoSpec(aspect="9:16", fps=5, start=4.0, end=5.0))
    assert out.exists() and out.stat().st_size > 1000
    with pytest.raises(ValueError):
        render_video(tiny_config, wav, tmp_path / "bad.mp4", VideoSpec(start=5.0, end=4.0))
