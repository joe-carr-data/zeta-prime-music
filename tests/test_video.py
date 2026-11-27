import shutil

import numpy as np
import pytest

from zeta_music import video
from zeta_music.video import VideoSpec, _traced, _window, frame_count, render_video


def test_window_loop_and_sliding(tiny_config):
    assert _window(tiny_config, 1, 5.0) == (1.5, 20.0)  # loop section: whole bar
    lo, hi = _window(tiny_config, 2, 30.0)  # 20..40 span <= 40: whole range
    assert (lo, hi) == (20.0, 40.0)


@pytest.mark.parametrize(("dur", "fps", "expected"), [(0.1, 5, 1), (1.3, 5, 7), (2.0, 5, 10), (1e-6, 30, 1)])
def test_frame_count_covers_partial_frames(dur, fps, expected):
    """Regression: int(dur*fps) gave 0 frames for sub-frame clips and dropped partial frames."""
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
    """Regression: an encoder that dies used to leak BrokenPipeError past the CLI."""
    monkeypatch.setattr(video, "_ffmpeg_cmd", lambda *a, **k: ["sh", "-c", "echo boom >&2; exit 3"])
    with pytest.raises(RuntimeError, match=r"exit 3.*boom"):
        render_video(tiny_config, tiny_wav, tmp_path / "x.mp4", VideoSpec(fps=5, start=4.0, end=5.0))


@needs_ffmpeg
def test_clip_audio_comes_from_the_requested_interval(tiny_config, tiny_wav, tmp_path):
    """Regression: the clip's audio must be the source's [start, end), not just any audio."""
    import subprocess

    import soundfile as sf

    out = render_video(tiny_config, tiny_wav, tmp_path / "v.mp4", VideoSpec(fps=5, start=3.0, end=6.0))
    dec = tmp_path / "dec.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-ac", "1", "-ar", "8000", str(dec)], check=True)
    clip, _ = sf.read(dec)
    src, sr = sf.read(tiny_wav)
    src = src.mean(axis=1)

    def env(a):
        blk = sr // 20
        return np.array([np.sqrt(np.mean(a[i : i + blk] ** 2)) for i in range(0, len(a) - blk, blk)])

    e_clip = env(clip)
    scores = {}
    for start in (1.0, 2.0, 3.0, 4.0):
        e_src = env(src[int(start * sr) : int((start + 3.0) * sr)])
        n = min(e_clip.size, e_src.size)
        scores[start] = np.corrcoef(e_clip[:n], e_src[:n])[0, 1]
    assert max(scores, key=scores.get) == 3.0 and scores[3.0] > 0.9


def test_sliding_window_follows_direction_and_stays_in_section():
    """long sweeps slide with the direction of travel and never leave the section."""
    from zeta_music.config import CompositionConfig, Section

    cfg = CompositionConfig(
        title="w", sections=[Section("up", 10.0, 2.0, 200.0, 50, 50), Section("down", 10.0, 200.0, 2.0, 50, 50)]
    )
    up_lo, up_hi = _window(cfg, 0, 100.0)
    assert up_hi - up_lo == 40 and up_lo < 100 < up_hi and 100 - up_lo > up_hi - 100  # mostly behind (left)
    dn_lo, dn_hi = _window(cfg, 1, 100.0)
    assert dn_hi - dn_lo == 40 and dn_lo < 100 < dn_hi and dn_hi - 100 > 100 - dn_lo  # mostly behind (right)
    for sec in (0, 1):
        for x in (2.0, 3.0, 199.0, 200.0):
            lo, hi = _window(cfg, sec, x)
            assert lo >= 2.0 and hi <= 200.0 and lo <= x <= hi


def test_traced_part_depends_on_direction():
    xg = np.linspace(2, 10, 9)
    assert _traced(xg, 5.0, True).tolist() == [x <= 5 for x in xg]
    assert _traced(xg, 5.0, False).tolist() == [x >= 5 for x in xg]


def test_hero_schedule_grows_geometrically_then_holds():
    from zeta_music.animate import HeroSpec, hero_schedule

    spec = HeroSpec(fps=10, grow=2.0, hold=1.0, fade=0.5, max_zeros=200)
    n = hero_schedule(spec)
    assert n.size == 20 + 15
    assert n[0] == 1.0 and n[19] == pytest.approx(200.0) and np.all(n[20:] == 200.0)
    assert np.all(np.diff(n[:20]) > 0)


@needs_ffmpeg
def test_render_hero_smoke(tmp_path):
    from zeta_music.animate import HeroSpec, render_hero

    gif = render_hero(
        tmp_path / "h.gif", HeroSpec(width=320, height=160, fps=4, grow=1.0, hold=0.5, fade=0.5, max_zeros=20)
    )
    assert gif.exists() and gif.read_bytes()[:6] in (b"GIF89a", b"GIF87a")


@needs_ffmpeg
def test_caption_and_end_card_render(tiny_config, tiny_wav, tmp_path):
    out = render_video(
        tiny_config, tiny_wav, tmp_path / "c.mp4",
        VideoSpec(aspect="9:16", fps=5, start=3.0, end=7.0, caption="Costs $5 or $x^$ — literal", end_card=True),
    )  # fmt: skip
    assert int({s["codec_type"]: s for s in _probe(out)["streams"]}["video"]["nb_read_frames"]) == 20


@needs_ffmpeg
def test_landscape_caption_renders(tiny_config, tiny_wav, tmp_path):
    out = render_video(tiny_config, tiny_wav, tmp_path / "l.mp4", VideoSpec(fps=5, start=3.0, end=4.0, caption="$x^$"))
    assert out.exists()
