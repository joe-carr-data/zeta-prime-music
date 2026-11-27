import shutil

import pytest

from zeta_music import video
from zeta_music.video import VideoSpec, _window, frame_count, render_video


def test_window_loop_and_sliding(tiny_config):
    assert _window(tiny_config, 1, 5.0) == (1.5, 20.0)  # loop section: whole bar
    lo, hi = _window(tiny_config, 2, 30.0)  # 20..40 span <= 40: whole range
    assert (lo, hi) == (20.0, 40.0)


@pytest.mark.parametrize(("dur", "fps", "expected"), [(0.1, 5, 1), (1.3, 5, 7), (2.0, 5, 10), (1e-6, 30, 1)])
def test_frame_count_covers_partial_frames(dur, fps, expected):
    """Regression : int(dur*fps) gave 0 frames for sub-frame clips and dropped partial frames."""
    assert frame_count(dur, fps) == expected


needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def tiny_wav(tiny_config, tmp_path):
    import soundfile as sf

    from zeta_music.composition import render

    res = render(tiny_config)
    wav = tmp_path / "a.wav"
    sf.write(wav, res.audio, res.sample_rate)
    return wav


def _probe(path):
    import json
    import subprocess

    out = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-show_entries",
         "stream=codec_type,nb_read_frames:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return json.loads(out.stdout)


@needs_ffmpeg
@pytest.mark.parametrize(
    ("start", "end", "frames"), [(4.0, 5.0, 5), (4.0, 4.1, 1), (4.0, 5.3, 7), (4.0, 5.201, 7), (4.0, 4.0001, 1)]
)
def test_render_video_streams_and_frames(tiny_config, tiny_wav, tmp_path, start, end, frames):
    out = render_video(tiny_config, tiny_wav, tmp_path / "v.mp4", VideoSpec(aspect="9:16", fps=5, start=start, end=end))
    info = _probe(out)
    kinds = {s["codec_type"]: s for s in info["streams"]}
    assert set(kinds) == {"video", "audio"}
    assert int(kinds["video"]["nb_read_frames"]) == frames
    assert float(info["format"]["duration"]) == pytest.approx(frames / 5, abs=0.15)


@needs_ffmpeg
def test_render_video_rejects_bad_ranges(tiny_config, tiny_wav, tmp_path):
    with pytest.raises(ValueError):
        render_video(tiny_config, tiny_wav, tmp_path / "bad.mp4", VideoSpec(start=5.0, end=4.0))
    with pytest.raises(ValueError):
        render_video(tiny_config, tiny_wav, tmp_path / "bad.mp4", VideoSpec(fps=0))


@needs_ffmpeg
def test_encoder_early_exit_is_a_runtime_error(tiny_config, tiny_wav, tmp_path, monkeypatch):
    """Regression : an encoder that dies used to leak BrokenPipeError past the CLI."""
    monkeypatch.setattr(video, "_ffmpeg_cmd", lambda *a, **k: ["sh", "-c", "echo boom >&2; exit 3"])
    with pytest.raises(RuntimeError, match=r"exit 3.*boom"):
        render_video(tiny_config, tiny_wav, tmp_path / "x.mp4", VideoSpec(fps=5, start=4.0, end=5.0))
