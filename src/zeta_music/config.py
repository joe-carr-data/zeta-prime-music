"""Typed composition configuration, loaded from TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

__all__ = ["CompositionConfig", "MixConfig", "Section", "load_config"]

Sweep = Literal["linear", "exp"]
Taper = Literal["none", "hann", "gauss", "fejer"]


@dataclass(frozen=True)
class Section:
    """A span of the piece.

    The "number line" variable ``x`` is swept from ``x_start`` to ``x_end``. If ``loop`` is
    set, the sweep repeats every ``loop`` seconds (an ostinato over the same integers).
    The number of zeros used grows/shrinks geometrically from ``zeros_start`` to
    ``zeros_end``; with ``zeros_steps`` it changes in discrete steps (one per loop).
    """

    name: str
    duration: float
    x_start: float
    x_end: float
    zeros_start: int
    zeros_end: int
    sweep: Sweep = "linear"
    loop: float | None = None
    zeros_steps: list[int] | None = None
    drone_gain: float = 1.0
    pluck_gain: float = 1.0
    breath_gain: float = 1.0

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise ValueError(f"section {self.name!r}: duration must be > 0")
        if min(self.x_start, self.x_end) <= 1.0:
            raise ValueError(f"section {self.name!r}: x must stay > 1")
        if min(self.zeros_start, self.zeros_end) < 0:
            raise ValueError(f"section {self.name!r}: zero counts must be >= 0")
        if self.loop is not None and self.loop <= 0:
            raise ValueError(f"section {self.name!r}: loop must be > 0")


@dataclass(frozen=True)
class MixConfig:
    drone_db: float = -12.0
    pluck_db: float = -6.0
    bell_db: float = -14.0
    breath_db: float = -26.0
    pole_db: float = -20.0
    reverb_mix: float = 0.22
    reverb_t60: float = 3.4
    peak_db: float = -1.0


@dataclass(frozen=True)
class CompositionConfig:
    title: str
    sections: list[Section]
    sample_rate: int = 44100
    seed: int = 1859  # year of Riemann's paper
    control_rate: int = 2000
    drone_base_hz: float = 110.0  # frequency assigned to gamma_1
    drone_exponent: float = 1.0  # f_k = base * (gamma_k/gamma_1) ** exponent
    drone_max_hz: float = 6000.0
    drone_tremolo: float = 0.35
    pluck_base_hz: float = 196.0  # fundamental whose harmonics give the prime pitches
    taper: Taper = "gauss"
    peak_prominence: float = 0.18  # relative to log(x) scale, see composition.detect_events
    mix: MixConfig = field(default_factory=MixConfig)

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.sections)

    @property
    def max_zeros(self) -> int:
        counts = [max(s.zeros_start, s.zeros_end, *(s.zeros_steps or [0])) for s in self.sections]
        return max(counts, default=0)


def _build(cls: type, data: dict[str, Any]) -> Any:
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown {cls.__name__} keys: {sorted(unknown)}")
    return cls(**data)


def load_config(path: str | Path) -> CompositionConfig:
    raw = tomllib.loads(Path(path).read_text())
    sections = [_build(Section, s) for s in raw.pop("sections", [])]
    if not sections:
        raise ValueError("config needs at least one [[sections]] entry")
    mix = _build(MixConfig, raw.pop("mix", {}))
    return _build(CompositionConfig, {**raw, "sections": sections, "mix": mix})
