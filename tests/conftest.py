from pathlib import Path

import pytest

from zeta_music.config import CompositionConfig, MixConfig, Section

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tiny_config() -> CompositionConfig:
    """A short, low-sample-rate piece that exercises every section feature."""
    return CompositionConfig(
        title="tiny",
        sample_rate=8000,
        control_rate=1000,
        sections=[
            Section("a", 2.0, 1.2, 2.5, 0, 1, pluck_gain=0.0),
            Section("b", 4.0, 1.5, 20.0, 1, 50, loop=2.0, zeros_steps=[5, 50]),
            Section("c", 2.0, 20.0, 40.0, 50, 80, sweep="exp"),
        ],
        drone_max_hz=3000.0,
        mix=MixConfig(reverb_t60=0.5),
    )
