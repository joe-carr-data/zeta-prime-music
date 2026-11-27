"""Typed composition configuration, loaded from TOML."""

from __future__ import annotations

import math
import tomllib
from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

__all__ = ["CompositionConfig", "MixConfig", "Section", "config_from_dict", "load_config"]

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
        _finite(self, "duration", "x_start", "x_end", "drone_gain", "pluck_gain", "breath_gain")
        if self.duration <= 0:
            raise ValueError("duration must be > 0")
        if min(self.x_start, self.x_end) <= 1.0:
            raise ValueError("x_start and x_end must be > 1 (the explicit formula lives on x > 1)")
        if self.sweep not in ("linear", "exp"):
            raise ValueError(f"sweep must be 'linear' or 'exp', got {self.sweep!r}")
        for key in ("zeros_start", "zeros_end"):
            _nonneg_int(self, key, getattr(self, key))
        if self.zeros_steps is not None:
            if not self.zeros_steps:
                raise ValueError("zeros_steps must not be empty (omit it instead)")
            for v in self.zeros_steps:
                _nonneg_int(self, "zeros_steps", v)
        if self.loop is not None:
            _finite(self, "loop")
            if self.loop <= 0:
                raise ValueError("loop must be > 0")
        for key in ("drone_gain", "pluck_gain", "breath_gain"):
            if getattr(self, key) < 0:
                raise ValueError(f"{key} must be >= 0")


def _finite(obj: object, *keys: str) -> None:
    for key in keys:
        v = getattr(obj, key)
        if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
            raise ValueError(f"{key} must be a finite number, got {v!r}")


def _nonneg_int(obj: object, key: str, v: object) -> None:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ValueError(f"{key} must be a non-negative integer, got {v!r}")


@dataclass(frozen=True)
class MixConfig:
    drone_db: float = -12.0
    pluck_db: float = -6.0
    bell_db: float = -9.0  # a unit-salience bell sits (bell_db - pluck_db) below a unit pluck
    breath_db: float = -26.0
    pole_db: float = -20.0
    reverb_mix: float = 0.22
    reverb_t60: float = 3.4
    peak_db: float = -1.0

    def __post_init__(self) -> None:
        for key in ("drone_db", "pluck_db", "bell_db", "breath_db", "pole_db"):
            v = getattr(self, key)  # -inf mutes a voice; +inf / NaN are errors
            if isinstance(v, bool) or not isinstance(v, int | float) or math.isnan(v) or v == math.inf:
                raise ValueError(f"{key} must be a number or -inf, got {v!r}")
        _finite(self, "reverb_mix", "reverb_t60", "peak_db")
        if self.reverb_t60 < 0.05:
            raise ValueError("reverb_t60 must be >= 0.05 s")
        if not 0.0 <= self.reverb_mix <= 1.0:
            raise ValueError("reverb_mix must be in [0, 1]")
        if self.reverb_t60 <= 0:
            raise ValueError("reverb_t60 must be > 0")
        if self.peak_db > 0:
            raise ValueError("peak_db must be <= 0 dBFS")


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

    def __post_init__(self) -> None:
        if not self.sections:
            raise ValueError("at least one section is required")
        for key in ("sample_rate", "control_rate"):
            v = getattr(self, key)
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                raise ValueError(f"{key} must be a positive integer, got {v!r}")
        if self.sample_rate < 8000:
            raise ValueError("sample_rate must be >= 8000 Hz (the breath band needs 250-2500 Hz)")
        _finite(self, "drone_base_hz", "drone_exponent", "drone_max_hz", "drone_tremolo", "pluck_base_hz")
        _finite(self, "peak_prominence")
        # Frequencies above ~0.45*sample_rate are skipped at render time (never aliased), so only the
        # fundamentals themselves must be representable.
        for key in ("drone_base_hz", "pluck_base_hz"):
            if not 0 < getattr(self, key) < 0.45 * self.sample_rate:
                raise ValueError(
                    f"{key} must be in (0, {0.45 * self.sample_rate:.0f}) Hz at sample_rate {self.sample_rate}"
                )
        if self.drone_max_hz <= 0:
            raise ValueError("drone_max_hz must be > 0 (partials above 0.45*sample_rate are dropped anyway)")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative integer, got {self.seed!r}")
        for i, sec in enumerate(self.sections):
            if round(sec.duration * self.control_rate) < 2:
                raise ValueError(
                    f"sections[{i}] ({sec.name!r}): duration {sec.duration} s is shorter than 2 control frames"
                )
            if sec.loop is not None and sec.loop * self.control_rate < 2:
                raise ValueError(f"sections[{i}] ({sec.name!r}): loop {sec.loop} s is shorter than 2 control frames")
        if self.drone_exponent <= 0:
            raise ValueError("drone_exponent must be > 0")
        if not 0.0 <= self.drone_tremolo <= 1.0:
            raise ValueError("drone_tremolo must be in [0, 1]")
        if self.taper not in ("none", "hann", "gauss", "fejer"):
            raise ValueError(f"taper must be one of none/hann/gauss/fejer, got {self.taper!r}")
        if self.peak_prominence <= 0:
            raise ValueError("peak_prominence must be > 0")

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.sections)

    @property
    def max_zeros(self) -> int:
        counts = [max(s.zeros_start, s.zeros_end, *(s.zeros_steps or [0])) for s in self.sections]
        return max(counts, default=0)


def _build(cls: type, data: dict[str, Any], where: str) -> Any:
    """Construct ``cls`` from TOML data; every error names the offending TOML location."""
    if not isinstance(data, dict):
        raise ValueError(f"{where}: expected a table")
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}")
    required = {f.name for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING}
    missing = required - set(data)
    if missing:
        raise ValueError(f"{where}: missing keys {sorted(missing)}")
    try:
        return cls(**data)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{where}: {exc}") from None


def load_config(path: str | Path) -> CompositionConfig:
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: invalid TOML: {exc}") from None
    return config_from_dict(raw, str(path))


def config_from_dict(raw: dict[str, Any], where: str) -> CompositionConfig:
    """Build a config from already-parsed TOML data (``where`` prefixes every error message)."""
    raw = dict(raw)
    path = where
    raw_sections = raw.pop("sections", [])
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError(f"{path}: needs at least one [[sections]] entry")
    sections = [
        _build(
            Section, s, f"{path}: sections[{i}]" + (f" ({s['name']!r})" if isinstance(s, dict) and "name" in s else "")
        )
        for i, s in enumerate(raw_sections)
    ]
    mix = _build(MixConfig, raw.pop("mix", {}), f"{path}: [mix]")
    return _build(CompositionConfig, {**raw, "sections": sections, "mix": mix}, str(path))
