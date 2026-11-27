"""Produced versions of a piece: tempo grid, instruments, arrangement, mix and master.

The engine (``composition.analyse``) still decides every note: when a peak of the truncated
explicit formula occurs, at which point of the number line, how in tune it is and how loud. This
module only decides *how those notes are played*:

* **Tempo grid.** The piece keeps its mathematical onsets; a MIDI tempo map (tempo, metre, section
  markers) makes them line up in a DAW. :func:`grid_bpm` picks the tempo at which the integers of
  a looping bar fall exactly on a sixteenth-note grid (8 s / 30 integers -> 112.5 BPM, 3 bars of 5/4).
* **Two tunings.** ``just`` keeps the exact pitches (one MIDI channel per sounding note, pitch bend
  ±2 st); ``tempered`` snaps every note to 12-TET (no bends), for players and sample libraries.
* **Instruments.** Each voice (primes, bells, drone, bass, sub, pulse, zeros) is played by a
  General MIDI SoundFont preset (FluidSynth), an AU/VST3 instrument (pedalboard, with a saved
  plugin state), a built-in sine, or the engine's own synthesis.
* **Mix and master.** Per-voice loudness normalisation, gain, filters and FX, a shared reverb send,
  a gentle bus compressor, then gain staging and a true-peak look-ahead limiter to a loudness
  target (ITU-R BS.1770 via ``pyloudnorm``).
"""

from __future__ import annotations

import functools
import hashlib
import itertools
import json
import logging
import os
import shutil
import subprocess
import tempfile
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import mido
import numpy as np
from numpy.lib import format as npy_format
from numpy.typing import NDArray
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d

from . import synth
from .composition import Event, Timeline
from .config import CompositionConfig, config_from_dict
from .midi import BEND_RANGE, midi_text

__all__ = [
    "ROLES",
    "Control",
    "FxSpec",
    "Note",
    "Part",
    "ProduceConfig",
    "SectionArrangement",
    "TempoMap",
    "VoiceSpec",
    "build_parts",
    "compress",
    "grid_bpm",
    "limit",
    "load_score",
    "lufs_gain_db",
    "note_for",
    "part_messages",
    "produce",
    "save_plugin_state",
    "true_peak_db",
    "write_midi_file",
]

log = logging.getLogger(__name__)
Audio = NDArray[np.float64]

ROLES = ("primes", "bells", "drone", "bass", "sub", "pulse", "zeros")
TUNINGS = ("just", "tempered")
PULSE_PATTERNS = ("off", "cycle", "bar", "groove")
BASS_PATTERNS = ("pedal", "drive")
MELODIC_CHANNELS = tuple(c for c in range(16) if c != 9)
DRUM_CHANNEL = 9
# General MIDI percussion keys used by the pulse
KICK, SIDE_STICK, CLOSED_HAT, CRASH, MARACAS = 36, 37, 42, 49, 70
DRONE_ZEROS = 8  # the first eight zeros form the sustained chord (E2 B2 D3 F3 G3 A3 Bb3 B3, see FOR_MUSICIANS)


# --------------------------------------------------------------------------------------
# Tempo
# --------------------------------------------------------------------------------------
def grid_bpm(loop_s: float, integers: float, sixteenths_per_integer: int = 2) -> float:
    """Tempo at which consecutive integers of a looping bar are ``sixteenths_per_integer`` apart.

    The bar sweeps ``integers`` whole numbers in ``loop_s`` seconds; with 8 s and 30 integers and two
    sixteenths per integer, a sixteenth is 1/7.5 s and a quarter note 0.5333 s: 112.5 BPM.
    """
    sixteenth = loop_s / integers / sixteenths_per_integer
    return 60.0 / (4.0 * sixteenth)


@dataclass(frozen=True)
class TempoMap:
    """Piecewise-constant tempo map: ``segments`` is ``((start_s, bpm), ...)`` starting at 0 s.

    Tempo is in quarter notes per minute (the MIDI convention), whatever the metre's denominator.
    """

    segments: tuple[tuple[float, float], ...]
    meter: tuple[int, int] = (4, 4)
    ppq: int = 960

    def __post_init__(self) -> None:
        if not self.segments or self.segments[0][0] != 0.0:
            raise ValueError("tempo map must start at 0 s")
        times = [t for t, _ in self.segments]
        if any(b <= a for a, b in itertools.pairwise(times)):
            raise ValueError("tempo changes must be strictly increasing in time")
        if any(not bpm > 0 for _, bpm in self.segments):
            raise ValueError("bpm must be > 0")
        num, den = self.meter
        if num <= 0 or den not in (1, 2, 4, 8, 16, 32):
            raise ValueError(f"bad metre {self.meter}")

    @classmethod
    def constant(cls, bpm: float, meter: tuple[int, int] = (4, 4), ppq: int = 960) -> TempoMap:
        return cls(((0.0, float(bpm)),), meter, ppq)

    def _starts(self) -> list[tuple[float, float, float]]:
        """(start_s, start_tick, ticks_per_second) per segment."""
        out, tick = [], 0.0
        for i, (t0, bpm) in enumerate(self.segments):
            tps = bpm / 60.0 * self.ppq
            out.append((t0, tick, tps))
            if i + 1 < len(self.segments):
                tick += (self.segments[i + 1][0] - t0) * tps
        return out

    def ticks(self, seconds: float) -> float:
        for t0, k0, tps in reversed(self._starts()):
            if seconds >= t0:
                return k0 + (seconds - t0) * tps
        return seconds * self._starts()[0][2]

    def seconds(self, ticks: float) -> float:
        for t0, k0, tps in reversed(self._starts()):
            if ticks >= k0:
                return t0 + (ticks - k0) / tps
        return ticks / self._starts()[0][2]

    @property
    def bar_ticks(self) -> int:
        num, den = self.meter
        return int(num * self.ppq * 4 // den)

    def grid_ticks(self, division: int) -> float:
        """Length of one 1/``division`` note in ticks (16 -> a sixteenth)."""
        return self.ppq * 4.0 / division

    def quantiser(self, division: int) -> Callable[[float], float]:
        g = self.grid_ticks(division)
        return lambda t: self.seconds(round(self.ticks(t) / g) * g)


# --------------------------------------------------------------------------------------
# Score
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FxSpec:
    """An effect: ``plugin`` is an AU/VST3 path or ``pedalboard:<Effect>`` (e.g. pedalboard:Chorus)."""

    plugin: str
    state: str | None = None
    plugin_name: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VoiceSpec:
    """How one voice is played. ``instrument``: ``sf2``, ``sf2:PATH``, ``plugin:PATH``, ``builtin:sine``, ``engine``."""

    name: str
    instrument: str
    bank: int | None = None  # None: send no bank select (a plugin keeps the preset in its state)
    program: int | None = None  # None: send no program change
    state: str | None = None
    plugin_name: str | None = None
    tuning: str | None = None  # force "tempered" for an instrument without per-channel pitch bend
    gain_db: float = 0.0
    send: float = 0.0
    highpass_hz: float | None = None
    lowpass_hz: float | None = None
    transpose: float = 0.0  # semitones
    presence_db: float = 0.0  # high shelf at 3.5 kHz
    load_wait: float = 3.0  # s to let a plugin instrument load its samples before rendering
    fx: tuple[FxSpec, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)  # plugin instrument parameters (e.g. a Massive patch)

    def __post_init__(self) -> None:
        if self.name not in ROLES:
            raise ValueError(f"unknown voice {self.name!r}; voices are {', '.join(ROLES)}")
        if self.kind not in ("sf2", "plugin", "builtin", "engine"):
            raise ValueError(f"voice {self.name!r}: unknown instrument {self.instrument!r}")
        if self.kind == "builtin" and self.instrument != "builtin:sine":
            raise ValueError(f"voice {self.name!r}: the only builtin instrument is 'builtin:sine'")
        if self.tuning is not None and self.tuning not in TUNINGS:
            raise ValueError(f"voice {self.name!r}: tuning must be one of {TUNINGS}")
        if not 0.0 <= self.send <= 1.0:
            raise ValueError(f"voice {self.name!r}: send must be in [0, 1]")
        if self.program is not None and not 0 <= self.program <= 127:
            raise ValueError(f"voice {self.name!r}: program must be 0-127")
        if self.bank is not None and not 0 <= self.bank <= 16383:
            raise ValueError(f"voice {self.name!r}: bank must be 0-16383")
        if self.load_wait < 0:
            raise ValueError(f"voice {self.name!r}: load_wait must be >= 0")
        if (self.name == "zeros") != (self.kind == "engine"):
            raise ValueError("the 'zeros' voice (and only it) uses instrument = 'engine'")

    @property
    def kind(self) -> str:
        return self.instrument.split(":", 1)[0]

    @property
    def target(self) -> str | None:
        return self.instrument.split(":", 1)[1] if ":" in self.instrument else None

    @property
    def drums(self) -> bool:
        return self.name == "pulse"


@dataclass(frozen=True)
class SectionArrangement:
    levels: dict[str, float]
    bass_pattern: str = "pedal"
    pulse: str = "off"
    gain_db: float = 0.0  # mix automation for the whole section (applied to every stem)

    def level(self, voice: str) -> float:
        if voice == "pulse":
            return 0.0 if self.pulse == "off" else 1.0
        if voice == "sub":
            return self.levels.get("sub", self.levels.get("bass", 0.0))
        return self.levels.get(voice, 0.0)


@dataclass(frozen=True)
class ProduceConfig:
    voices: dict[str, VoiceSpec]
    arrangement: dict[str, SectionArrangement]
    bpm: float = 112.5
    meter: tuple[int, int] = (5, 4)
    quantise: int = 16
    tail: float = 8.0
    target_lufs: float = -14.0
    true_peak_db: float = -1.0
    reverb_t60: float = 2.4
    bus_threshold_db: float = -16.0
    bus_ratio: float = 2.0
    soundfont: str | None = None
    master_fx: tuple[FxSpec, ...] = ()
    master_air_db: float = 0.0  # high shelf at 8 kHz on the mix bus
    master_low_db: float = 0.0  # low shelf at 150 Hz on the mix bus

    def __post_init__(self) -> None:
        def num(key: str) -> float:
            v = getattr(self, key)
            if isinstance(v, bool) or not isinstance(v, int | float) or not np.isfinite(v):
                raise ValueError(f"[produce] {key} must be a finite number, got {v!r}")
            return float(v)

        if num("bus_ratio") < 1.0:
            raise ValueError("[produce] bus_ratio must be >= 1 (1 = no compression)")
        if num("bus_threshold_db") > 0.0:
            raise ValueError("[produce] bus_threshold_db must be <= 0 dBFS")
        if not -40.0 <= num("target_lufs") <= -5.0:
            raise ValueError("[produce] target_lufs must be in [-40, -5]")
        if not -12.0 <= num("true_peak_db") <= 0.0:
            raise ValueError("[produce] true_peak_db must be in [-12, 0] dBTP")
        if num("tail") < 0.0:
            raise ValueError("[produce] tail must be >= 0 s")
        if num("reverb_t60") < 0.05:
            raise ValueError("[produce] reverb_t60 must be >= 0.05 s")
        for key in ("master_air_db", "master_low_db"):
            if abs(num(key)) > 12.0:
                raise ValueError(f"[produce] {key} must be within +-12 dB")
        if num("bpm") <= 0:
            raise ValueError("[produce] bpm must be > 0")

    @property
    def tempo(self) -> TempoMap:
        return TempoMap.constant(self.bpm, self.meter)


_PRODUCE_KEYS = {
    "bpm",
    "meter",
    "quantise",
    "tail",
    "target_lufs",
    "true_peak_db",
    "reverb_t60",
    "bus_threshold_db",
    "bus_ratio",
    "soundfont",
    "voices",
    "arrangement",
    "master_fx",
    "master_air_db",
    "master_low_db",
}


def _fx_list(raw: Any, where: str) -> tuple[FxSpec, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"{where}: fx must be a list of tables")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or "plugin" not in item:
            raise ValueError(f"{where}: fx[{i}] needs a 'plugin' key")
        unknown = set(item) - {"plugin", "state", "plugin_name", "params"}
        if unknown:
            raise ValueError(f"{where}: fx[{i}] unknown keys {sorted(unknown)}")
        out.append(FxSpec(**item))
    return tuple(out)


def produce_config_from_dict(raw: dict[str, Any], cfg: CompositionConfig, where: str) -> ProduceConfig:
    raw = dict(raw)
    unknown = set(raw) - _PRODUCE_KEYS
    if unknown:
        raise ValueError(f"{where}: [produce] unknown keys {sorted(unknown)}")
    voices: dict[str, VoiceSpec] = {}
    for name, v in raw.pop("voices", {}).items():
        if not isinstance(v, dict):
            raise ValueError(f"{where}: [produce.voices.{name}] must be a table")
        v = dict(v)
        fx = _fx_list(v.pop("fx", []), f"{where}: [produce.voices.{name}]")
        try:
            voices[name] = VoiceSpec(name=name, fx=fx, **v)
        except TypeError as exc:
            raise ValueError(f"{where}: [produce.voices.{name}]: {exc}") from None
        except ValueError as exc:
            raise ValueError(f"{where}: {exc}") from None
    if not voices:
        raise ValueError(f"{where}: [produce] needs at least one voice")
    names = {s.name for s in cfg.sections}
    arrangement: dict[str, SectionArrangement] = {}
    for sec, a in raw.pop("arrangement", {}).items():
        if sec not in names:
            raise ValueError(f"{where}: [produce.arrangement] section {sec!r} is not in the score")
        a = dict(a)
        pulse = a.pop("pulse", "off")
        bass_pattern = a.pop("bass_pattern", "pedal")
        gain_db = a.pop("gain_db", 0.0)
        if isinstance(gain_db, bool) or not isinstance(gain_db, int | float) or not -24 <= gain_db <= 24:
            raise ValueError(f"{where}: section {sec!r}: gain_db must be a number in [-24, 24]")
        if pulse not in PULSE_PATTERNS:
            raise ValueError(f"{where}: section {sec!r}: pulse must be one of {PULSE_PATTERNS}")
        if bass_pattern not in BASS_PATTERNS:
            raise ValueError(f"{where}: section {sec!r}: bass_pattern must be one of {BASS_PATTERNS}")
        bad = set(a) - set(ROLES)
        if bad:
            raise ValueError(f"{where}: section {sec!r}: unknown voices {sorted(bad)}")
        levels = {k: float(x) for k, x in a.items()}
        if any(not 0.0 <= x <= 4.0 for x in levels.values()):
            raise ValueError(f"{where}: section {sec!r}: voice levels must be in [0, 4]")
        arrangement[sec] = SectionArrangement(levels, bass_pattern, pulse, float(gain_db))
    master_fx = _fx_list(raw.pop("master_fx", []), f"{where}: [produce]")
    meter = tuple(raw.pop("meter", (5, 4)))
    if len(meter) != 2:
        raise ValueError(f"{where}: meter must be [numerator, denominator]")
    try:
        pc = ProduceConfig(voices, arrangement, meter=(int(meter[0]), int(meter[1])), master_fx=master_fx, **raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{where}: {exc}") from None
    pc.tempo  # validates bpm and metre  # noqa: B018
    if pc.quantise not in (4, 8, 16, 32):
        raise ValueError(f"{where}: quantise must be 4, 8, 16 or 32")
    return pc


def load_score(path: str | Path) -> tuple[CompositionConfig, ProduceConfig]:
    """Load an engine score that also carries a ``[produce]`` table."""
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: invalid TOML: {exc}") from None
    prod_raw = raw.pop("produce", None)
    if prod_raw is None:
        raise ValueError(f"{path}: no [produce] table (see compositions/commercial/critical_strip_radio.toml)")
    cfg = config_from_dict(raw, str(path))
    return cfg, produce_config_from_dict(prod_raw, cfg, str(path))


# --------------------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Note:
    time: float  # s, onset (the mathematical time for primes and bells)
    dur: float  # s
    freq: float  # exact Hz (tempering happens at MIDI time); ignored for drums
    velocity: int
    pan: float = 0.0  # -1..1, used per note when each note has its own channel
    key: int | None = None  # GM drum key (pulse only)
    tempered_key: int | None = None  # MIDI key to use in the tempered tuning (re-voiced drone)


@dataclass(frozen=True)
class Control:
    time: float
    cc: int
    value: int


@dataclass
class Part:
    voice: str
    notes: list[Note] = field(default_factory=list)
    controls: list[Control] = field(default_factory=list)
    drums: bool = False


def section_spans(cfg: CompositionConfig) -> list[tuple[str, float, float]]:
    out, t = [], 0.0
    for s in cfg.sections:
        out.append((s.name, t, t + s.duration))
        t += s.duration
    return out


def _arr_at(prod: ProduceConfig, cfg: CompositionConfig, t: float) -> tuple[str, SectionArrangement]:
    spans = section_spans(cfg)
    name = spans[-1][0]
    for n, a, b in spans:
        if a <= t < b:
            name = n
            break
    return name, prod.arrangement.get(name, SectionArrangement({}))


def _vel(x: float) -> int:
    return int(np.clip(round(x), 1, 127))


def primes_part(events: Sequence[Event], cfg: CompositionConfig, prod: ProduceConfig) -> Part:
    """Primes (and ghosts, the not-yet-in-tune peaks) at their exact times and pitches."""
    part = Part("primes")
    for e in events:
        if e.kind == "prime_power":
            continue
        level = _arr_at(prod, cfg, e.time)[1].level("primes")
        if level <= 0:
            continue
        sal = min(max(e.salience, 0.0), 1.15)
        if e.kind == "ghost":
            part.notes.append(Note(e.time, 0.7, e.freq, _vel((28 + 70 * sal) * 0.7 * level), e.pan))
        else:
            part.notes.append(Note(e.time, 2.2, e.freq, _vel((30 + 85 * sal) * level), e.pan))
    return part


def bells_part(events: Sequence[Event], cfg: CompositionConfig, prod: ProduceConfig) -> Part:
    """Prime powers an octave up (their spikes are 1/k as tall: velocity follows salience)."""
    part = Part("bells")
    for e in events:
        if e.kind != "prime_power":
            continue
        level = _arr_at(prod, cfg, e.time)[1].level("bells")
        if level > 0:
            sal = min(max(e.salience, 0.0), 1.0)
            part.notes.append(Note(e.time, 3.0, e.freq * 2.0, _vel((40 + 100 * sal) * level), -e.pan))
    return part


def _runs(mask: NDArray[np.bool_]) -> list[tuple[int, int]]:
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist(), strict=True))


def drone_part(cfg: CompositionConfig, tl: Timeline, gammas: NDArray[np.float64], prod: ProduceConfig) -> Part:
    """The first zeros as a sustained chord: zero k sounds while at least k+1 zeros are switched on.

    Velocity follows the zero's explicit-formula weight 1/|rho_k|; while the first zero fades in
    (fewer than one zero), CC11 expression follows the fractional count. Notes re-articulate at
    every section start.
    """
    part = Part("drone")
    g = np.asarray(gammas[:DRONE_ZEROS], dtype=float)
    weights = np.abs(complex(0.5, g[0])) / np.abs(0.5 + 1j * g)
    freqs = cfg.drone_base_hz * g / g[0]
    voiced = open_voicing([note_for(float(f), "tempered")[0] for f in freqs])
    for name, a, b in section_spans(cfg):
        level = prod.arrangement.get(name, SectionArrangement({})).level("drone")
        if level <= 0:
            continue
        i0, i1 = round(a * tl.rate), round(b * tl.rate)
        n = tl.n_zeros[i0:i1]
        for k in range(g.size):
            mask = n > 0 if k == 0 else n >= k + 1 - 1e-9
            vk = voiced[k]
            tk = -1 if vk is None else vk  # -1: dropped from the tempered chord
            for r0, r1 in _runs(mask):
                t0, t1 = a + r0 / tl.rate, a + r1 / tl.rate
                vel = _vel((42 + 60 * weights[k] ** 0.5) * level)
                part.notes.append(Note(t0, t1 - t0, float(freqs[k]), vel, tempered_key=tk))
    # fade-in of the first zero (fractional count < 1) as expression; full expression otherwise
    frac = np.clip(tl.n_zeros, 0.0, 1.0)
    step = int(0.25 * tl.rate)
    last = -1
    for j in range(0, tl.n_zeros.size, step):
        v = round(127 * np.sqrt(frac[j]))
        if v != last:
            part.controls.append(Control(j / tl.rate, 11, v))
            last = v
    return part


def open_voicing(keys: Sequence[int], max_key: int = 96) -> list[int | None]:
    """Re-voice a tempered chord so no two tones form a minor/major second or a minor ninth.

    Tones are taken from the bottom up; a tone that clashes with one already placed moves up an
    octave until it fits (or is dropped above ``max_key``). The just version is never re-voiced:
    there the zeros' exact, inharmonic ratios are the point.
    """
    placed: list[int] = []
    out: list[int | None] = [None] * len(keys)
    for i in sorted(range(len(keys)), key=lambda j: keys[j]):
        cand = int(keys[i])
        while any(abs(cand - p) < 3 or abs(cand - p) == 13 for p in placed):
            cand += 12
        if cand <= max_key:
            placed.append(cand)
            out[i] = cand
    return out


def bass_part(cfg: CompositionConfig, prod: ProduceConfig, voice: str = "bass") -> Part:
    """Bass on the drone's root E (the first zero, an octave down), one note per bar on the grid.

    ``pedal``: E1 held for the bar. ``drive``: E1 on beat 1 and E2 on beat 4 (the 3+2 of 5/4);
    the last bar of each 8 s cycle answers with G1, the primes' tonic.
    """
    part = Part(voice)
    tempo = prod.tempo
    beat = 60.0 / prod.bpm * 4.0 / prod.meter[1]
    bar = beat * prod.meter[0]
    e1 = cfg.drone_base_hz / 2.0
    g1 = cfg.pluck_base_hz / 2.0
    bars_per_cycle = _bars_per_cycle(cfg, bar)
    for name, a, b in section_spans(cfg):
        arr = prod.arrangement.get(name, SectionArrangement({}))
        level = arr.level(voice)
        if level <= 0:
            continue
        for t in _bar_starts(a, b, bar):
            idx = round(tempo.ticks(t) / tempo.bar_ticks)
            v = _vel(96 * level)
            if arr.bass_pattern == "pedal" or prod.meter[0] < 4:
                part.notes.append(Note(t, bar * 0.96, e1, v))
            else:
                split = 3 if prod.meter[0] == 5 else prod.meter[0] // 2
                part.notes.append(Note(t, beat * split * 0.95, e1, v))
                answer = g1 if bars_per_cycle and idx % bars_per_cycle == bars_per_cycle - 1 else 2 * e1
                part.notes.append(Note(t + beat * split, beat * (prod.meter[0] - split) * 0.92, answer, _vel(v * 0.85)))
    return part


def sub_part(cfg: CompositionConfig, prod: ProduceConfig) -> Part:
    """Sine sub: the bass pattern at the sections' ``sub`` level (default: the bass level), folded below 60 Hz."""
    notes = []
    for nt in bass_part(cfg, prod, "sub").notes:
        f = nt.freq
        while f > 60.0:
            f /= 2.0
        notes.append(Note(nt.time, nt.dur, f, nt.velocity))
    return Part("sub", notes)


def _bars_per_cycle(cfg: CompositionConfig, bar: float) -> int:
    loops = {s.loop for s in cfg.sections if s.loop}
    if len(loops) == 1:
        q = next(iter(loops)) / bar
        if abs(q - round(q)) < 1e-6:
            return round(q)
    return 0


def _bar_starts(a: float, b: float, bar: float) -> list[float]:
    k0 = int(np.ceil(a / bar - 1e-9))
    out = []
    k = k0
    while k * bar < b - 1e-9:
        out.append(k * bar)
        k += 1
    return out


def pulse_part(cfg: CompositionConfig, prod: ProduceConfig) -> Part:
    """Sparse percussion on eighth notes only.

    With the grid tempo every integer of the bar sits on an odd sixteenth, so eighth notes fall on
    the half-integers, where no prime (or prime power) can sound: the pulse never masks the primes.
    ``cycle``: one soft kick per 8 s cycle. ``bar``: kick per bar and a quiet maracas line.
    ``groove``: kick on beats 1 and 4, side stick on 3 and 5, maracas eighths, a crash at the
    section start.
    """
    part = Part("pulse", drums=True)
    rng = np.random.default_rng(cfg.seed + 11)
    eighth = 60.0 / prod.bpm / 2.0
    beat = 60.0 / prod.bpm * 4.0 / prod.meter[1]
    bar = beat * prod.meter[0]
    eighths_per_bar = round(bar / eighth)
    bars_per_cycle = _bars_per_cycle(cfg, bar) or 1
    tempo = prod.tempo

    def hit(t: float, key: int, v: float) -> None:
        part.notes.append(Note(t, eighth * 0.9, 0.0, _vel(v + rng.integers(-5, 6)), key=key))

    for name, a, b in section_spans(cfg):
        arr = prod.arrangement.get(name, SectionArrangement({}))
        pattern = arr.pulse
        if pattern == "off":
            continue
        first = True
        for t in _bar_starts(a, b, bar):
            idx = round(tempo.ticks(t) / tempo.bar_ticks)
            if pattern == "cycle":
                if idx % bars_per_cycle == 0:
                    hit(t, KICK, 62)
                continue
            if pattern == "groove" and first:
                hit(t, CRASH, 58)
            first = False
            for i in range(eighths_per_bar):
                te = t + i * eighth
                if te >= b - 1e-9:
                    break
                on_beat = i % 2 == 0
                hit(te, MARACAS, 40 if on_beat else 26)
                if pattern == "bar" and i == 0:
                    hit(te, KICK, 74)
                if pattern == "groove":
                    if (i in (0, 6) and prod.meter[0] == 5) or (prod.meter[0] != 5 and i % 4 == 0):
                        hit(te, KICK, 80 if i == 0 else 66)
                    if (i in (4, 8) and prod.meter[0] == 5) or (prod.meter[0] != 5 and i % 4 == 2):
                        hit(te, SIDE_STICK, 56)
    part.notes.sort(key=lambda n: n.time)
    return part


def build_parts(
    cfg: CompositionConfig,
    prod: ProduceConfig,
    tl: Timeline,
    gammas: NDArray[np.float64],
    events: Sequence[Event],
) -> dict[str, Part]:
    """Every voice's notes, derived from the engine's analysis and the arrangement."""
    parts: dict[str, Part] = {}
    builders: dict[str, Callable[[], Part]] = {
        "primes": lambda: primes_part(events, cfg, prod),
        "bells": lambda: bells_part(events, cfg, prod),
        "drone": lambda: drone_part(cfg, tl, gammas, prod),
        "bass": lambda: bass_part(cfg, prod),
        "sub": lambda: sub_part(cfg, prod),
        "pulse": lambda: pulse_part(cfg, prod),
    }
    for name in prod.voices:
        if name in builders:
            parts[name] = builders[name]()
    return parts


# --------------------------------------------------------------------------------------
# MIDI
# --------------------------------------------------------------------------------------
def note_for(freq: float, tuning: str, transpose: float = 0.0) -> tuple[int, int]:
    """(MIDI note, pitch-bend value) for ``freq``: exact (bend, ±BEND_RANGE st) or 12-TET (no bend)."""
    if tuning not in TUNINGS:
        raise ValueError(f"tuning must be one of {TUNINGS}")
    m = 69.0 + 12.0 * np.log2(freq / 440.0) + transpose
    note = int(np.clip(round(m), 0, 127))
    if tuning == "tempered":
        return note, 0
    bend = int(np.clip(round((m - note) / BEND_RANGE * 8192), -8192, 8191))
    return note, bend


Msg = tuple[float, int, mido.Message]  # (seconds, order at equal time, message)
MIN_NOTE_S = 2e-3  # shorter notes are dropped (several MIDI ticks at any tempo this module writes)


def _allocate(notes: Sequence[tuple[float, float, int]], channels: Sequence[int]) -> list[tuple[int, float, float]]:
    """Channel and (possibly shortened) off time per note.

    Several channels: every note gets a channel to itself while it sounds (its bend is private),
    the longest-free channel first; with all busy the voice ending soonest is stolen (its note-off
    pulled to the new onset). One channel: polyphony on that channel; only a repeated key cuts the
    previous instance of the same key.
    """
    out: list[list[float]] = []
    if len(channels) == 1:
        last_of_key: dict[int, int] = {}
        for on, off, key in notes:
            j = last_of_key.get(key)
            if j is not None and out[j][2] > on:
                out[j][2] = on
            last_of_key[key] = len(out)
            out.append([channels[0], on, off])
        return [(int(c), a, b) for c, a, b in out]
    free_at = dict.fromkeys(channels, -1.0)
    owner: dict[int, int] = {}
    for on, off, _key in notes:
        idle = [c for c in channels if free_at[c] <= on]
        if idle:
            ch = min(idle, key=lambda c: free_at[c])
        else:
            ch = min(channels, key=lambda c: free_at[c])
            out[owner[ch]][2] = on
        owner[ch] = len(out)
        free_at[ch] = off
        out.append([ch, on, off])
    return [(int(c), a, b) for c, a, b in out]


def part_messages(
    part: Part,
    voice: VoiceSpec,
    tuning: str,
    channels: Sequence[int],
    quantise: Callable[[float], float] | None = None,
) -> list[Msg]:
    """Timed MIDI messages (seconds) for one voice, including setup (bank/program/RPN/volume)."""
    if voice.tuning is not None:
        tuning = voice.tuning
    if part.drums:
        channels = [DRUM_CHANNEL]
    q = quantise or (lambda t: t)
    msgs: list[Msg] = []
    for ch in channels:
        if voice.bank is not None and not part.drums:  # MSB/LSB (FluidSynth runs in MMA bank mode)
            msgs.append((0.0, -3, mido.Message("control_change", channel=ch, control=0, value=(voice.bank >> 7) & 127)))
            msgs.append((0.0, -3, mido.Message("control_change", channel=ch, control=32, value=voice.bank & 127)))
        if voice.program is not None:
            msgs.append((0.0, -2, mido.Message("program_change", channel=ch, program=voice.program)))
        if tuning == "just" and not part.drums:
            for ctl, val in ((101, 0), (100, 0), (6, int(BEND_RANGE)), (38, 0), (101, 127), (100, 127)):
                msgs.append((0.0, -2, mido.Message("control_change", channel=ch, control=ctl, value=val)))
        msgs.append((0.0, -2, mido.Message("control_change", channel=ch, control=7, value=100)))
        msgs.append((0.0, -2, mido.Message("control_change", channel=ch, control=10, value=64)))
        msgs.append((0.0, -2, mido.Message("control_change", channel=ch, control=11, value=127)))
    notes = sorted(part.notes, key=lambda n: n.time)
    keyed = []
    for nt in notes:
        on = q(nt.time)
        if part.drums:
            key, bend = int(nt.key or KICK), 0
        elif tuning == "tempered" and nt.tempered_key is not None:
            if nt.tempered_key < 0:
                continue  # tone dropped from the tempered voicing
            key, bend = int(np.clip(nt.tempered_key + round(voice.transpose), 0, 127)), 0
        else:
            key, bend = note_for(nt.freq, tuning, voice.transpose)
        keyed.append((on, on + nt.dur, key, bend, nt))
    alloc = _allocate([(on, off, key) for on, off, key, _, _ in keyed], list(channels))
    per_note_channel = len(channels) > 1
    for (ch, on, off), (_, _, key, bend, nt) in zip(alloc, keyed, strict=True):
        if off - on < MIN_NOTE_S:
            # cut to (almost) nothing by a later note on the same key/channel (e.g. two onsets that
            # quantise to one tick): drop it, so every note-off precedes the next note-on
            continue
        if per_note_channel:
            pan = int(np.clip(round(64 + 50 * nt.pan), 0, 127))
            msgs.append((on, 0, mido.Message("control_change", channel=ch, control=10, value=pan)))
        if tuning == "just" and not part.drums:
            msgs.append((on, 1, mido.Message("pitchwheel", channel=ch, pitch=bend)))
        msgs.append((on, 2, mido.Message("note_on", channel=ch, note=key, velocity=nt.velocity)))
        msgs.append((off, -1, mido.Message("note_off", channel=ch, note=key, velocity=0)))
    used = sorted({c for c, _, _ in alloc}) or list(channels)
    for c in part.controls:
        for ch in used:
            msgs.append((q(c.time), 0, mido.Message("control_change", channel=ch, control=c.cc, value=c.value)))
    msgs.sort(key=lambda m: (m[0], m[1]))
    return msgs


def _channels_for(voice: VoiceSpec, tuning: str, slot: int) -> list[int]:
    if voice.drums:
        return [DRUM_CHANNEL]
    if (voice.tuning or tuning) == "just":
        return list(MELODIC_CHANNELS)
    return [MELODIC_CHANNELS[slot % len(MELODIC_CHANNELS)]]


def write_midi_file(
    path: Path,
    title: str,
    parts: Sequence[tuple[VoiceSpec, Part]],
    tempo: TempoMap,
    tuning: str,
    markers: Sequence[tuple[float, str]] = (),
    quantise: int | None = None,
) -> Path:
    """Type-1 MIDI: a tempo track (tempo map, metre, section markers) and one track per voice.

    Channel plan: every voice track in a multi-track file carries its own MIDI port meta event
    (port = track slot), so tracks never share a port's channels. A ``just`` voice uses all 15
    melodic channels of its port (one per sounding note, exact pitch bends); a ``tempered`` voice
    one channel (the slot's), drums channel 10, no bends.
    """
    mid = mido.MidiFile(type=1, ticks_per_beat=tempo.ppq)
    head = mido.MidiTrack()
    mid.tracks.append(head)
    head.append(mido.MetaMessage("track_name", name=midi_text(title), time=0))
    num, den = tempo.meter
    head_events: list[tuple[int, mido.MetaMessage]] = [
        (0, mido.MetaMessage("time_signature", numerator=num, denominator=den, clocks_per_click=24)),
    ]
    for t0, bpm in tempo.segments:
        head_events.append((round(tempo.ticks(t0)), mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))))
    for t, text in markers:
        head_events.append((round(tempo.ticks(t)), mido.MetaMessage("marker", text=midi_text(text))))
    _append_sorted(head, [(k, i, m) for i, (k, m) in enumerate(head_events)])
    qfn = tempo.quantiser(quantise) if quantise else None
    for slot, (voice, part) in enumerate(parts):
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=voice.name, time=0))
        if len(parts) > 1:
            track.append(mido.MetaMessage("midi_port", port=slot % 128, time=0))
        msgs = part_messages(part, voice, tuning, _channels_for(voice, tuning, slot), qfn)
        _append_sorted(track, [(round(tempo.ticks(t)), o, m) for t, o, m in msgs])
    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(path)
    return path


def _append_sorted(track: mido.MidiTrack, items: list[tuple[int, int, Any]]) -> None:
    items.sort(key=lambda x: (x[0], x[1]))
    last = 0
    for tick, _, msg in items:
        track.append(msg.copy(time=max(tick - last, 0)))
        last = max(tick, last)
    track.append(mido.MetaMessage("end_of_track", time=0))


# --------------------------------------------------------------------------------------
# Instruments
# --------------------------------------------------------------------------------------
def _expand(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))


def _fit(audio: Audio, n: int) -> Audio:
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    audio = audio[:, :2]
    if audio.shape[0] >= n:
        return audio[:n].copy()
    return np.concatenate([audio, np.zeros((n - audio.shape[0], 2))])


def fluidsynth_cmd(exe: str, sf2: Path, mid: Path, wav: Path, sr: int) -> list[str]:
    """Offline FluidSynth render: its reverb/chorus off, float output, and MMA bank select
    (CC0 = MSB, CC32 = LSB) so a configured bank is honoured (the default GS mode ignores CC32)."""
    cmd = [exe, "-ni", "-q", "-R", "0", "-C", "0", "-g", "0.5", "-r", str(sr), "-O", "float", "-T", "wav"]
    cmd += ["-o", "synth.polyphony=512", "-o", "synth.midi-bank-select=mma"]
    return [*cmd, "-F", str(wav), str(sf2), str(mid)]


def render_sf2(
    sf2: Path, part: Part, voice: VoiceSpec, tuning: str, tempo: TempoMap, sr: int, n: int, workdir: Path
) -> Audio:
    """Render one voice with FluidSynth (offline, its own reverb and chorus off)."""
    import soundfile as sf

    exe = shutil.which("fluidsynth")
    if exe is None:
        raise RuntimeError("fluidsynth not found on PATH (macOS: brew install fluid-synth)")
    if not sf2.is_file():
        raise FileNotFoundError(f"SoundFont not found: {sf2}")
    mid = write_midi_file(workdir / f"{voice.name}.mid", voice.name, [(voice, part)], tempo, tuning)
    wav = workdir / f"{voice.name}.wav"
    try:
        subprocess.run(fluidsynth_cmd(exe, sf2, mid, wav, sr), check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode(errors="replace").strip() or f"exit status {exc.returncode}"
        raise RuntimeError(f"fluidsynth failed rendering voice {voice.name!r}: {err}") from None
    audio, file_sr = sf.read(wav, always_2d=True, dtype="float32")
    wav.unlink()
    mid.unlink()
    if file_sr != sr:
        raise RuntimeError(f"fluidsynth wrote {file_sr} Hz, expected {sr}")
    return _fit(audio, n)


def _load_plugin(path: str, plugin_name: str | None, state: str | None, params: dict[str, Any] | None = None) -> Any:
    try:
        import pedalboard
    except ImportError as exc:
        raise RuntimeError("plugins need pedalboard: uv sync --extra produce") from exc
    if path.startswith("pedalboard:"):
        cls = getattr(pedalboard, path.split(":", 1)[1], None)
        if cls is None:
            raise ValueError(f"unknown pedalboard effect {path!r}")
        return cls(**(params or {}))
    file = _expand(path)
    if not file.exists():
        raise FileNotFoundError(f"plugin not found: {file}")
    try:
        plugin = pedalboard.load_plugin(
            str(file), plugin_name=plugin_name, parameter_values=params or None, initialization_timeout=30.0
        )
    except ImportError as exc:  # pedalboard reports every load failure as ImportError
        raise RuntimeError(f"could not load {file}: {exc}") from None
    if state:
        plugin.raw_state = _expand(state).read_bytes()
    return plugin


PLUGIN_PREROLL = 2.0  # s of silence rendered (and discarded) before a plugin instrument plays


def render_plugin(part: Part, voice: VoiceSpec, tuning: str, sr: int, n: int) -> Audio:
    """Render one voice through an AU/VST3 instrument (pedalboard), restoring its saved state."""
    assert voice.target is not None
    import time

    plugin = _load_plugin(voice.target, voice.plugin_name, voice.state, voice.params)
    if not getattr(plugin, "is_instrument", False):
        raise ValueError(f"voice {voice.name!r}: {voice.target} is not an instrument plugin")
    # Sample players (Kontakt) stream their library in the background after a state restore:
    # wait, then render ONE continuous buffer that starts with PLUGIN_PREROLL s of silence (the
    # warm-up) and trim it off, so nothing resets the plugin between warm-up and piece. No bank or
    # program message is sent unless the voice configures one, so the restored preset stays.
    time.sleep(voice.load_wait)
    msgs = part_messages(part, voice, tuning, _channels_for(voice, tuning, 0))
    events = [(m.bytes(), float(t) + PLUGIN_PREROLL) for t, _, m in msgs]
    audio = plugin(events, duration=n / sr + PLUGIN_PREROLL, sample_rate=sr, num_channels=2, buffer_size=512)
    audio = np.asarray(audio, dtype=np.float32).T[round(PLUGIN_PREROLL * sr) :]
    return _fit(audio, n)


def sine_freq(freq: float, tuning: str, transpose: float = 0.0) -> float:
    """Frequency a sine voice plays: transposed, and snapped to 12-TET in the tempered tuning."""
    f = freq * 2.0 ** (transpose / 12.0)
    if tuning == "tempered":
        f = 440.0 * 2.0 ** ((round(69 + 12 * np.log2(f / 440.0)) - 69) / 12.0)
    return float(f)


def render_sine(part: Part, sr: int, n: int, tuning: str = "just", transpose: float = 0.0) -> Audio:
    """Pure sine notes with 8 ms attack and 80 ms release (velocity -> amplitude, squared)."""
    out = np.zeros(n, dtype=np.float32)
    for nt in part.notes:
        freq = sine_freq(nt.freq, tuning, transpose)
        a = int(nt.time * sr)
        m = int((nt.dur + 0.08) * sr)
        t = np.arange(m) / sr
        env = np.minimum(1.0, t / 0.008) * np.clip((nt.dur + 0.08 - t) / 0.08, 0.0, 1.0)
        tone = np.sin(2 * np.pi * freq * t) * env * (nt.velocity / 127.0) ** 2
        b = min(a + m, n)
        if a < n:
            out[a:b] += tone[: b - a]
    return np.stack([out, out], axis=1)


def apply_fx(audio: Audio, sr: int, chain: Sequence[FxSpec]) -> Audio:
    for fx in chain:
        plugin = _load_plugin(fx.plugin, fx.plugin_name, fx.state, fx.params)
        audio = np.asarray(plugin(audio.T.astype(np.float32), sr), dtype=np.float64).T
    return audio


def save_plugin_state(plugin_path: str, out: Path, plugin_name: str | None = None, state: str | None = None) -> Path:
    """Open a plugin's editor so a person can choose a preset/library, then save its raw state."""
    plugin = _load_plugin(plugin_path, plugin_name, state)
    plugin.show_editor()  # blocks until the window is closed
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(plugin.raw_state)
    return out


# --------------------------------------------------------------------------------------
# Render cache and parallel plugin rendering
# --------------------------------------------------------------------------------------
# The cache holds each voice's RAW instrument audio: what the instrument (plugin, SoundFont or
# engine) produced, before per-voice FX, loudness normalisation, filters, gain, automation, send
# and mastering. Everything after that stage is cheap and runs on every render, so a mix, FX,
# arrangement-level or mastering change re-renders no instrument, and a change to one voice's
# notes or instrument re-renders only that voice. The key is a SHA-256 of everything that
# affects the raw audio (see :func:`render_key`). Builtin sine voices are not cached (they render
# in milliseconds).
CACHE_VERSION = 1  # bump when instrument rendering changes in a way the key cannot see
DEFAULT_CACHE_DIR = Path("output/cache")
_ENGINE_SOURCES = ("composition.py", "synth.py", "explicit.py", "zeros.py", "config.py", "data/zeros.txt")


_UMASK = os.umask(0o022)
os.umask(_UMASK)


class RenderError(RuntimeError):
    """A voice failed to render (in this process or in a worker process)."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _digest(spec: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=repr).encode()).hexdigest()


def _event_list(msgs: Sequence[Msg]) -> list[tuple[float, int, str]]:
    """MIDI messages as plain data (s, order, bytes): keys, bends, velocities, channels, controllers."""
    return [(float(t), int(o), bytes(m.bytes()).hex()) for t, o, m in msgs]


def _engine_code_digest() -> str:
    root = Path(__file__).parent
    h = hashlib.sha256()
    for rel in _ENGINE_SOURCES:
        h.update(rel.encode())
        h.update((root / rel).read_bytes())
    return h.hexdigest()


def render_key(
    voice: VoiceSpec,
    part: Part | None,
    tuning: str,
    sr: int,
    n: int,
    *,
    soundfont: Path | None = None,
    tempo: TempoMap | None = None,
    cfg: CompositionConfig | None = None,
) -> str:
    """Stable cache key of one voice's raw instrument audio.

    Plugin: the MIDI events actually sent (times, keys, bends, velocities, channels, controllers),
    tuning, transpose, sample rate, length, plugin path and name, SHA-256 of the state file's
    bytes, parameter values, load_wait and the pre-roll. SoundFont: the events, the
    tempo map (MIDI ticks), the SoundFont's path and SHA-256. Engine: the whole composition config
    and a digest of the engine's source files. Always: :data:`CACHE_VERSION`. Gain, send, filters,
    FX and the voice's name are deliberately not part of the key.
    """
    spec: dict[str, Any] = {"salt": CACHE_VERSION, "kind": voice.kind, "sr": int(sr), "n": int(n)}
    if voice.kind == "engine":
        if cfg is None:
            raise ValueError("the engine voice's key needs the composition config")
        return _digest(spec | {"config": asdict(cfg), "engine_code": _engine_code_digest()})
    if part is None:
        raise ValueError(f"voice {voice.name!r}: no part to key")
    msgs = part_messages(part, voice, tuning, _channels_for(voice, tuning, 0))
    spec |= {"tuning": voice.tuning or tuning, "transpose": float(voice.transpose), "events": _event_list(msgs)}
    if voice.kind == "plugin":
        assert voice.target is not None
        state = None
        if voice.state:
            sp = _expand(voice.state)
            if not sp.is_file():
                raise FileNotFoundError(f"voice {voice.name!r}: plugin state not found: {sp}")
            state = _sha256_file(sp)
        spec |= {
            "plugin": str(_expand(voice.target)),
            "plugin_name": voice.plugin_name,
            "state_sha256": state,
            "params": voice.params,
            "load_wait": float(voice.load_wait),
            "preroll": PLUGIN_PREROLL,
        }
    elif voice.kind == "sf2":
        if soundfont is None or tempo is None:
            raise ValueError("a SoundFont voice's key needs the SoundFont and the tempo map")
        if not soundfont.is_file():
            raise FileNotFoundError(f"SoundFont not found: {soundfont}")
        spec |= {
            "soundfont": str(soundfont),
            "soundfont_sha256": _sha256_file(soundfont),
            "tempo": [list(tempo.segments), list(tempo.meter), tempo.ppq],
        }
    else:
        raise ValueError(f"voice {voice.name!r}: {voice.instrument} is not cached")
    return _digest(spec)


def _atomic_write(path: Path, write: Callable[[Any], None], mode: str = "wb") -> Path:
    """Write via a temporary file in the same directory and a rename: readers see the old file,
    no file, or the complete new one, never a partial write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.chmod(tmp, 0o666 & ~_UMASK)  # mkstemp creates 0600; give the file the usual permissions
        with os.fdopen(fd, mode) as f:
            write(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def atomic_save(path: Path, audio: NDArray[np.floating[Any]]) -> Path:
    """Save ``audio`` atomically as a float32 ``.npy`` file."""
    data = np.ascontiguousarray(audio, dtype=np.float32)
    return _atomic_write(path, lambda f: np.save(f, data, allow_pickle=False))


class RenderCache:
    """Raw voice audio on disk: ``<key>.npy`` (float32, frames x 2) plus a ``<key>.json`` note."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path(self, key: str) -> Path:
        return self.root / f"{key}.npy"

    def has(self, key: str, n: int) -> bool:
        """A complete float32 (n, 2) entry exists (checked from the header and file size, not read)."""
        p = self.path(key)
        try:
            with open(p, "rb") as f:
                version = npy_format.read_magic(f)
                if version == (1, 0):
                    shape, fortran, dtype = npy_format.read_array_header_1_0(f)
                else:
                    shape, fortran, dtype = npy_format.read_array_header_2_0(f)
                offset = f.tell()
        except (OSError, ValueError):
            return False
        ok = shape == (n, 2) and dtype == np.float32 and not fortran
        return ok and p.stat().st_size == offset + n * 2 * 4

    def load(self, key: str, n: int) -> NDArray[np.float32] | None:
        p = self.path(key)
        if not self.has(key, n):
            if p.exists():
                log.warning("ignoring incomplete or mismatched cache entry %s", p)
            return None
        try:
            audio = np.load(p, allow_pickle=False)
        except (OSError, ValueError, EOFError) as exc:
            log.warning("ignoring unreadable cache entry %s: %s", p, exc)
            return None
        if audio.dtype != np.float32 or audio.shape != (n, 2):
            log.warning("ignoring cache entry %s (dtype %s, shape %s)", p, audio.dtype, audio.shape)
            return None
        return audio

    def store(self, key: str, audio: NDArray[np.floating[Any]]) -> Path:
        return atomic_save(self.path(key), audio)

    def describe(self, key: str, info: dict[str, Any]) -> None:
        text = json.dumps(info, indent=1)
        _atomic_write(self.path(key).with_suffix(".json"), lambda f: f.write(text), "w")


def clear_cache(root: Path = DEFAULT_CACHE_DIR) -> int:
    """Delete every cache entry under ``root``; returns the number of files removed."""
    root = Path(root)
    if not root.is_dir():
        return 0
    removed = 0
    for p in root.iterdir():
        if p.is_file() and (p.suffix in (".npy", ".json") or p.name.endswith(".tmp")):
            p.unlink()
            removed += 1
    return removed


Renderer = Callable[[Part, VoiceSpec, str, int, int], Audio]


@dataclass(frozen=True)
class RenderJob:
    """One plugin voice to render into ``out``. Picklable: it crosses into a worker process, so
    ``renderer`` must be a module-level function."""

    key: str
    voice: VoiceSpec
    part: Part
    tuning: str
    sr: int
    n: int
    out: Path
    renderer: Renderer


def run_job(job: RenderJob) -> Path:
    """Render one job and save its audio atomically; any failure becomes a :class:`RenderError`."""
    try:
        return atomic_save(job.out, _fit(job.renderer(job.part, job.voice, job.tuning, job.sr, job.n), job.n))
    except RenderError:
        raise
    except Exception as exc:  # e.g. a plugin that fails to load; the message must pickle back from a worker
        raise RenderError(
            f"rendering voice {job.voice.name!r} with {job.voice.instrument} failed: {type(exc).__name__}: {exc}"
        ) from None


def default_jobs(n_plugin_jobs: int) -> int:
    """min(plugin voices to render, half the CPUs, 4), at least 1."""
    return max(1, min(n_plugin_jobs, (os.cpu_count() or 2) // 2, 4))


def render_jobs(jobs: Sequence[RenderJob], workers: int, local: Sequence[Callable[[], None]] = ()) -> None:
    """Render plugin ``jobs`` in up to ``workers`` separate processes and the ``local`` callables here.

    Workers use the "spawn" start method and one job per process, so each loads its own plugin in a
    fresh process. Jobs with the most notes start first. Every job is a pure function of its inputs
    and writes its own file, so the result never depends on the number of workers or on the order
    of completion. The first failure stops the other workers and is raised as :class:`RenderError`
    naming the voice.
    """
    jobs = sorted(jobs, key=lambda j: -len(j.part.notes))
    if workers <= 1 or len(jobs) <= 1:
        for j in jobs:
            log.info("rendering %s with %s", j.voice.name, j.voice.instrument)
            run_job(j)
        for fn in local:
            fn()
        return
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from concurrent.futures.process import BrokenProcessPool

    workers = min(workers, len(jobs))
    log.info("rendering %d plugin voices in %d processes", len(jobs), workers)
    ex = ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn"), max_tasks_per_child=1)
    futures: dict[Any, RenderJob] = {}
    try:
        futures = {ex.submit(run_job, j): j for j in jobs}
        for fn in local:
            fn()
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                fut.result()
            except BrokenProcessPool:
                raise RenderError(
                    f"the process rendering voice {j.voice.name!r} with {j.voice.instrument} stopped unexpectedly"
                ) from None
            log.info("rendered %s", j.voice.name)
    except BaseException:
        for f in futures:
            f.cancel()
        # do not wait for a slow plugin render whose result is no longer needed
        for p in list((getattr(ex, "_processes", None) or {}).values()):
            p.terminate()
        ex.shutdown(wait=True, cancel_futures=True)
        raise
    ex.shutdown(wait=True)


# --------------------------------------------------------------------------------------
# Mix and master DSP
# --------------------------------------------------------------------------------------
def lufs_gain_db(measured_lufs: float, target_lufs: float) -> float:
    """Gain that moves integrated loudness from ``measured`` to ``target`` (loudness is linear in dB)."""
    if not np.isfinite(measured_lufs):
        return 0.0
    return float(target_lufs - measured_lufs)


def integrated_lufs(audio: Audio, sr: int) -> float:
    import pyloudnorm

    x = np.asarray(audio, dtype=np.float64)
    if x.shape[0] < int(0.4 * sr) or not np.any(x):  # shorter than one gating block, or silent
        return float("-inf")
    try:
        return float(pyloudnorm.Meter(sr).integrated_loudness(x))
    except ValueError:
        return float("-inf")


def _oversampled_peak(x: NDArray[np.float64], factor: int, chunk: int = 1 << 18) -> NDArray[np.float64]:
    """Per-sample peak of a mono signal after ``factor``x polyphase oversampling (chunked)."""
    pad = 64
    out = np.empty(x.size)
    for s in range(0, x.size, chunk):
        a, b = max(s - pad, 0), min(s + chunk + pad, x.size)
        up = signal.resample_poly(x[a:b], factor, 1)
        env = np.abs(up[: (b - a) * factor]).reshape(-1, factor).max(axis=1)
        out[s : min(s + chunk, x.size)] = env[s - a : s - a + min(chunk, x.size - s)]
    return np.maximum(out, np.abs(x))


def true_peak_db(audio: Audio, factor: int = 4) -> float:
    """True peak in dBTP (``factor``x oversampled, BS.1770 style)."""
    a = np.atleast_2d(np.asarray(audio, dtype=np.float64).T)
    peak = max(float(_oversampled_peak(ch, factor).max()) for ch in a)
    return float(20 * np.log10(peak)) if peak > 0 else -np.inf


def compress(
    audio: Audio,
    sr: int,
    threshold_db: float = -16.0,
    ratio: float = 2.0,
    attack: float = 0.03,
    release: float = 0.3,
    knee_db: float = 6.0,
) -> tuple[Audio, dict[str, float]]:
    """Gentle feed-forward bus compressor (stereo-linked RMS detector, soft knee, 1 ms control rate)."""
    if not ratio >= 1.0:
        raise ValueError("compressor ratio must be >= 1")
    if not (attack > 0 and release > 0 and knee_db >= 0):
        raise ValueError("compressor attack and release must be > 0 and knee >= 0")
    hop = max(sr // 1000, 1)
    p = np.mean(np.asarray(audio) ** 2, axis=1)
    rms = np.sqrt(np.maximum(uniform_filter1d(p, max(int(0.01 * sr), 1)), 0.0))[::hop]
    level = 20 * np.log10(rms + 1e-12)
    over = level - threshold_db
    slope = 1.0 - 1.0 / ratio
    gr = np.where(
        over <= -knee_db / 2,
        0.0,
        np.where(over >= knee_db / 2, slope * over, slope * (over + knee_db / 2) ** 2 / (2 * max(knee_db, 1e-9))),
    )
    ca, cr = np.exp(-hop / (attack * sr)), np.exp(-hop / (release * sr))
    sm = np.empty_like(gr)
    s = 0.0
    for i, v in enumerate(gr.tolist()):
        c = ca if v > s else cr
        s = c * s + (1.0 - c) * v
        sm[i] = s
    gain_db = np.interp(np.arange(p.size), np.arange(sm.size) * hop, -sm)
    stats = {"max_gr_db": float(sm.max(initial=0.0)), "mean_gr_db": float(sm.mean()) if sm.size else 0.0}
    return audio * (10 ** (gain_db / 20))[:, None], stats


def limit(
    audio: Audio,
    sr: int,
    ceiling_db: float = -1.0,
    lookahead: float = 0.005,
    release: float = 0.08,
    oversample: int = 4,
) -> Audio:
    """Look-ahead true-peak limiter.

    Required gain ``min(1, ceiling / true_peak_envelope)`` is min-filtered over the look-ahead
    window (forward in time), then averaged over the same window (backward), which keeps the gain
    at every peak at or below what that peak needs while ramping smoothly into it; a release
    stage lets it recover slowly. Offline, so no delay is introduced.

    The envelope is estimated on the input; the gain itself can shift intersample peaks slightly,
    so the OUTPUT's true peak is measured and, if it is still above the ceiling, the whole signal
    is trimmed by the (tiny) excess. The ceiling therefore holds on the output.
    """
    x = np.asarray(audio, dtype=np.float64)
    env = np.max([_oversampled_peak(ch, oversample) for ch in x.T], axis=0)
    ceiling = 10 ** (ceiling_db / 20)
    need = np.minimum(1.0, ceiling / np.maximum(env, 1e-12))
    h = max(int(lookahead * sr) // 2, 1)
    size = 2 * h + 1
    fwd = minimum_filter1d(need, size, origin=-h, mode="nearest")  # min over [n, n + 2h]
    # mean over [n - 2h, n]: every term is a min over a window containing n, so att[n] <= need[n]
    att = uniform_filter1d(fwd, size, origin=h, mode="nearest")
    block = 32
    nb = int(np.ceil(att.size / block))
    bmin = np.pad(att, (0, nb * block - att.size), constant_values=1.0).reshape(nb, block).min(axis=1)
    r = np.exp(-block / (release * sr))
    rel = np.empty(nb)
    s = 1.0
    for i, v in enumerate(bmin.tolist()):
        s = min(v, s * r + (1.0 - r))
        rel[i] = s
    g = np.minimum(att, np.interp(np.arange(att.size), np.arange(nb) * block, rel))
    y = x * g[:, None]
    for _ in range(3):
        tp = true_peak_db(y, oversample)
        if not tp > ceiling_db:
            break
        y *= 10 ** ((ceiling_db - tp - 1e-4) / 20)
    return y


def master_chain(
    mix: Audio, sr: int, prod: ProduceConfig, extra_headroom_db: float = 0.0
) -> tuple[Audio, dict[str, float]]:
    """High-pass, bus compression, gain staging to the loudness target, true-peak limiting."""
    sos = signal.butter(2, 25.0, btype="highpass", fs=sr, output="sos")
    x = signal.sosfiltfilt(sos, mix, axis=0)
    if prod.master_fx:
        x = apply_fx(x, sr, prod.master_fx)
    if prod.master_air_db:
        x = high_shelf(x, sr, 8000.0, prod.master_air_db)
    if prod.master_low_db:
        x = low_shelf(x, sr, 150.0, prod.master_low_db)
    if not np.any(x):
        raise RuntimeError("the arrangement is silent: nothing to master (check the voice levels)")
    x, comp = compress(x, sr, prod.bus_threshold_db, prod.bus_ratio)
    # the final fade is part of the programme: apply it BEFORE measuring and staging
    fade = min(int(2.0 * sr), x.shape[0] // 4)
    if fade > 0:
        x[-fade:] *= np.cos(np.linspace(0, np.pi / 2, fade))[:, None] ** 2
    measured = integrated_lufs(x, sr)
    staged = bool(np.isfinite(measured))  # too short / too quiet to measure: no gain staging
    gain = lufs_gain_db(measured, prod.target_lufs)
    ceiling = prod.true_peak_db - 0.3 - extra_headroom_db
    tries = 8
    for i in range(tries):
        y = limit(x * 10 ** (gain / 20), sr, ceiling)
        lufs = integrated_lufs(y, sr)
        if not staged or not np.isfinite(lufs) or abs(lufs - prod.target_lufs) < 0.1 or i == tries - 1:
            break  # y was rendered with exactly this gain and ceiling
        gain += prod.target_lufs - lufs
    if not np.all(np.isfinite(y)):
        raise RuntimeError("master contains NaN/inf samples")
    tp = true_peak_db(y)
    return y, {
        "integrated_lufs": round(lufs, 2) if np.isfinite(lufs) else None,
        "true_peak_dbtp": round(tp, 2),
        "sample_peak_dbfs": round(float(20 * np.log10(np.max(np.abs(y)))), 2),
        "pre_limiter_gain_db": round(gain, 2),
        "limiter_ceiling_dbtp": round(ceiling, 2),
        "bus_comp_max_gr_db": round(comp["max_gr_db"], 2),
        "bus_comp_mean_gr_db": round(comp["mean_gr_db"], 2),
    }


def _active_rms(audio: Audio, sr: int) -> float:
    p = np.mean(audio**2, axis=1)
    w = uniform_filter1d(p, max(int(0.05 * sr), 1))
    act = w > 1e-4 * w.max(initial=0.0)  # frames within 40 dB of the loudest: where the voice plays
    return float(np.sqrt(w[act].mean())) if act.any() else 0.0


def low_shelf(audio: Audio, sr: int, freq: float, gain_db: float, slope: float = 0.7) -> Audio:
    """Zero-phase RBJ low shelf: ``gain_db`` in total (each of the two filtfilt passes gets half)."""
    if gain_db == 0:
        return audio
    a_ = 10 ** (gain_db / 2 / 40)
    w0 = 2 * np.pi * freq / sr
    c, sq = np.cos(w0), np.sqrt(a_)
    alpha = np.sin(w0) / 2 * np.sqrt((a_ + 1 / a_) * (1 / slope - 1) + 2)
    b = np.array(
        [
            a_ * ((a_ + 1) - (a_ - 1) * c + 2 * sq * alpha),
            2 * a_ * ((a_ - 1) - (a_ + 1) * c),
            a_ * ((a_ + 1) - (a_ - 1) * c - 2 * sq * alpha),
        ]
    )
    a = np.array(
        [
            (a_ + 1) + (a_ - 1) * c + 2 * sq * alpha,
            -2 * ((a_ - 1) + (a_ + 1) * c),
            (a_ + 1) + (a_ - 1) * c - 2 * sq * alpha,
        ]
    )
    return signal.filtfilt(b / a[0], a / a[0], audio, axis=0)


def high_shelf(audio: Audio, sr: int, freq: float, gain_db: float, slope: float = 0.7) -> Audio:
    """Zero-phase RBJ high shelf: ``gain_db`` in total (each of the two filtfilt passes gets half)."""
    if gain_db == 0:
        return audio
    a_ = 10 ** (gain_db / 2 / 40)
    w0 = 2 * np.pi * freq / sr
    c, sq = np.cos(w0), np.sqrt(a_)
    alpha = np.sin(w0) / 2 * np.sqrt((a_ + 1 / a_) * (1 / slope - 1) + 2)
    b = np.array(
        [
            a_ * ((a_ + 1) + (a_ - 1) * c + 2 * sq * alpha),
            -2 * a_ * ((a_ - 1) + (a_ + 1) * c),
            a_ * ((a_ + 1) + (a_ - 1) * c - 2 * sq * alpha),
        ]
    )
    a = np.array(
        [
            (a_ + 1) - (a_ - 1) * c + 2 * sq * alpha,
            2 * ((a_ - 1) - (a_ + 1) * c),
            (a_ + 1) - (a_ - 1) * c - 2 * sq * alpha,
        ]
    )
    return signal.filtfilt(b / a[0], a / a[0], audio, axis=0)


def _filter(audio: Audio, sr: int, voice: VoiceSpec) -> Audio:
    if voice.presence_db:
        audio = high_shelf(audio, sr, 3500.0, voice.presence_db)
    if voice.highpass_hz:
        audio = signal.sosfiltfilt(signal.butter(2, voice.highpass_hz, "highpass", fs=sr, output="sos"), audio, axis=0)
    if voice.lowpass_hz:
        audio = signal.sosfiltfilt(signal.butter(2, voice.lowpass_hz, "lowpass", fs=sr, output="sos"), audio, axis=0)
    return audio


def _band_report(audio: Audio, sr: int) -> dict[str, float]:
    """Share of energy (dB re total) per band, from a Welch spectrum of the mono sum."""
    mono = audio.mean(axis=1)
    if not np.any(mono):
        return {}
    f, pxx = signal.welch(mono, sr, nperseg=8192)
    total = pxx.sum()
    bands = {"sub_<60": (0, 60), "low_60-250": (60, 250), "lowmid_250-2k": (250, 2000), "high_2k-8k": (2000, 8000)}
    bands["air_>8k"] = (8000, sr / 2)
    out = {
        k: round(float(10 * np.log10(pxx[(f >= a) & (f < b)].sum() / total + 1e-12)), 1) for k, (a, b) in bands.items()
    }
    out["centroid_hz"] = round(float((f * pxx).sum() / total), 0)
    return out


# --------------------------------------------------------------------------------------
# Top level
# --------------------------------------------------------------------------------------
def _section_gain_curve(
    cfg: CompositionConfig, prod: ProduceConfig, voice: str | None, sr: int, n: int
) -> NDArray[np.float32]:
    """Smoothed per-section level of ``voice`` (or, with ``voice=None``, the sections' gain_db automation)."""
    rate = 200  # control rate; the curve is smooth, interpolated to audio rate at the end
    m = int(np.ceil(n / sr * rate)) + 1
    g = np.zeros(m)
    for name, a, b in section_spans(cfg):
        arr = prod.arrangement.get(name, SectionArrangement({}))
        g[int(a * rate) : int(b * rate)] = arr.level(voice) if voice else 10 ** (arr.gain_db / 20)
    end = min(int(cfg.duration * rate), m - 1)
    g[end:] = g[end - 1]
    g = synth.smooth(g, rate, 0.6)
    return np.interp(np.arange(n) / sr, np.arange(m) / rate, g).astype(np.float32)


def produce(
    score: Path,
    out_dir: Path,
    tunings: Sequence[str] = ("just", "tempered"),
    soundfont: str | None = None,
    audio: bool = True,
    name: str | None = None,
    stem_format: str = "flac",
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    jobs: int | None = None,
) -> dict[str, Any]:
    """Build MIDI (just, tempered, tempered + quantised), stems and masters for a produced score.

    Masters are 24-bit WAV (+ 256 kb/s AAC). Stems (24-bit, ``flac`` by default: lossless and a
    fraction of the size, since most stems are silent much of the time) are written for the first
    tuning only; they share one gain, so summing them reproduces the pre-master mix.

    Each voice's raw instrument audio is cached in ``cache_dir`` (``None``: no persistent cache)
    and reused while its key is unchanged (see :func:`render_key`). Plugin voices missing from the
    cache render in up to ``jobs`` worker processes (default :func:`default_jobs`).
    """
    if stem_format not in ("flac", "wav"):
        raise ValueError("stem_format must be 'flac' or 'wav'")
    if jobs is not None and jobs < 1:
        raise ValueError("jobs must be >= 1")

    from .composition import analyse, render

    cfg, prod = load_score(score)
    stem = name or score.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    gammas, tl, _sal, events = analyse(cfg)
    parts = build_parts(cfg, prod, tl, gammas, events)
    tempo = prod.tempo
    markers = [(a, n) for n, a, _ in section_spans(cfg)]
    ordered = [(prod.voices[v], parts[v]) for v in prod.voices if v in parts]
    paths: dict[str, str] = {}
    paths["midi_just"] = str(write_midi_file(out_dir / f"{stem}_just.mid", cfg.title, ordered, tempo, "just", markers))
    paths["midi_tempered"] = str(
        write_midi_file(out_dir / f"{stem}_tempered.mid", cfg.title, ordered, tempo, "tempered", markers)
    )
    paths["midi_tempered_quantised"] = str(
        write_midi_file(
            out_dir / f"{stem}_tempered_quantised.mid", cfg.title, ordered, tempo, "tempered", markers, prod.quantise
        )
    )
    for voice, part in ordered:  # one file per voice: 15 channels each for MPE-style exact pitch
        p = write_midi_file(
            out_dir / "midi" / f"{stem}_{voice.name}_just.mid", cfg.title, [(voice, part)], tempo, "just", markers
        )
        paths[f"midi_just_{voice.name}"] = str(p)
    meta: dict[str, Any] = {
        "title": cfg.title,
        "tempo": {"bpm": prod.bpm, "meter": list(prod.meter), "bar_s": tempo.bar_ticks / tempo.ppq * 60 / prod.bpm},
        "sections": [{"name": n, "start_s": a, "end_s": b} for n, a, b in section_spans(cfg)],
        "notes": {v: len(p.notes) for v, p in parts.items()},
        "events": [asdict(e) | {"prime": e.prime} for e in events],
    }
    if not audio:
        (out_dir / f"{stem}.produce.json").write_text(json.dumps(meta | {"paths": paths}, indent=1))
        return meta | {"paths": paths}

    sr = cfg.sample_rate
    n = int((cfg.duration + prod.tail) * sr)
    sf2_default = soundfont or os.environ.get("ZETA_SOUNDFONT") or prod.soundfont
    automation = _section_gain_curve(cfg, prod, None, sr, n)[:, None]
    zeros_curve = _section_gain_curve(cfg, prod, "zeros", sr, n)[:, None] if "zeros" in prod.voices else None
    tmp_ctx = tempfile.TemporaryDirectory()
    tmp = Path(tmp_ctx.name)
    try:
        # without a cache directory the entries live in a temporary one for this run only (a voice
        # that sounds the same in both tunings is still rendered once)
        cache = RenderCache(cache_dir if cache_dir is not None else tmp / "cache")
        keys, render_info = _render_voices(cfg, prod, parts, tunings, sr, n, sf2_default, cache, jobs, tmp, render)
        render_info["cache_dir"] = str(cache_dir) if cache_dir is not None else None
        meta["render"] = render_info
        reports = _mix_and_master(
            cfg, prod, parts, tunings, sr, n, keys, cache, automation, zeros_curve, out_dir, stem, stem_format, paths
        )
    finally:
        tmp_ctx.cleanup()
    meta |= {"paths": paths, "reports": reports, "soundfont": str(_expand(sf2_default)) if sf2_default else None}
    (out_dir / f"{stem}.produce.json").write_text(json.dumps(meta, indent=1))
    return meta


def _render_engine_raw(render: Callable[..., Any], cfg: CompositionConfig, n: int) -> NDArray[np.float32]:
    """The engine's zero drone, breath and pole summed into one float32 buffer (before the zeros level)."""
    log.info("rendering the engine's zero drone, breath and pole")
    engine = render(cfg, stems=True).stems
    assert engine is not None
    out = np.zeros((n, 2), dtype=np.float32)
    for k in ("drone", "breath", "pole"):
        a_ = engine.pop(k)[:n]
        out[: a_.shape[0]] += a_.astype(np.float32)
        del a_
    return out


def _render_voices(
    cfg: CompositionConfig,
    prod: ProduceConfig,
    parts: dict[str, Part],
    tunings: Sequence[str],
    sr: int,
    n: int,
    sf2_default: str | None,
    cache: RenderCache,
    jobs: int | None,
    tmp: Path,
    render: Callable[..., Any],
) -> tuple[dict[tuple[str, str], str], dict[str, Any]]:
    """Key every (tuning, voice), render what the cache lacks (plugins in parallel), return the keys."""
    tempo = prod.tempo
    keys: dict[tuple[str, str], str] = {}
    labels: dict[str, list[str]] = {}
    plugin_jobs: dict[str, RenderJob] = {}
    local: dict[str, Callable[[], None]] = {}
    hits: set[str] = set()

    def store(key: str, make: Callable[[], Audio | NDArray[np.float32]]) -> None:
        cache.store(key, _fit(make(), n))

    for tuning in tunings:
        for vname, voice in prod.voices.items():
            if voice.kind == "builtin":
                continue
            sf2: Path | None = None
            if voice.kind == "sf2":
                name_ = voice.target or sf2_default
                if not name_:
                    raise ValueError(f"voice {vname!r}: no SoundFont (set [produce] soundfont or --soundfont)")
                sf2 = _expand(name_)
            part = parts.get(vname)
            key = render_key(voice, part, tuning, sr, n, soundfont=sf2, tempo=tempo, cfg=cfg)
            keys[(tuning, vname)] = key
            labels.setdefault(key, []).append(f"{tuning}:{vname}")
            if key in plugin_jobs or key in local or key in hits:
                continue
            if cache.has(key, n):
                hits.add(key)
            elif voice.kind == "plugin":
                assert part is not None
                plugin_jobs[key] = RenderJob(key, voice, part, tuning, sr, n, cache.path(key), render_plugin)
            elif voice.kind == "sf2":
                assert part is not None and sf2 is not None
                work = tmp / key
                work.mkdir()
                fn = functools.partial(render_sf2, sf2, part, voice, tuning, tempo, sr, n, work)
                local[key] = functools.partial(store, key, fn)
            else:
                local[key] = functools.partial(store, key, functools.partial(_render_engine_raw, render, cfg, n))
    workers = jobs if jobs is not None else default_jobs(len(plugin_jobs))
    if workers < 1:
        raise ValueError("jobs must be >= 1")
    rendered = [*plugin_jobs, *local]
    log.info("render cache %s: %d voices cached, %d to render", cache.root, len(hits), len(rendered))
    render_jobs(list(plugin_jobs.values()), workers, list(local.values()))
    for key in rendered:
        cache.describe(key, {"voices": labels[key], "cache_version": CACHE_VERSION})
    info = {
        "workers": workers,
        "rendered": sorted(lbl for k in rendered for lbl in labels[k]),
        "from_cache": sorted(lbl for k in hits for lbl in labels[k]),
    }
    return keys, info


def _mix_and_master(
    cfg: CompositionConfig,
    prod: ProduceConfig,
    parts: dict[str, Part],
    tunings: Sequence[str],
    sr: int,
    n: int,
    keys: dict[tuple[str, str], str],
    cache: RenderCache,
    automation: NDArray[np.float32],
    zeros_curve: NDArray[np.float32] | None,
    out_dir: Path,
    stem: str,
    stem_format: str,
    paths: dict[str, str],
) -> dict[str, Any]:
    """Per-voice FX and mix from the raw voice audio, reverb send, master, stems and reports."""
    import soundfile as sf

    reports: dict[str, Any] = {}
    stem_ceiling = 10 ** (-1.0 / 20)  # no stem file (and not their sum) above -1 dBFS
    for tuning in tunings:
        suffix = "" if tuning == tunings[0] else f"_{tuning}"
        stems: dict[str, NDArray[np.float32]] = {}
        send = np.zeros((n, 2), dtype=np.float32)
        mix = np.zeros((n, 2), dtype=np.float32)
        for vname, voice in prod.voices.items():
            if voice.kind == "builtin":
                raw = render_sine(parts[vname], sr, n, voice.tuning or tuning, voice.transpose)
            else:
                cached = cache.load(keys[(tuning, vname)], n)
                if cached is None:
                    raise RuntimeError(f"voice {vname!r}: rendered audio missing from {cache.root}")
                if voice.kind == "engine":
                    assert zeros_curve is not None
                    cached *= zeros_curve
                raw = cached.astype(np.float64)
                del cached
            raw = apply_fx(raw, sr, voice.fx) if voice.fx else raw
            rms = _active_rms(raw, sr)
            norm = (10 ** (-20 / 20)) / rms if rms > 0 else 0.0  # every voice to -20 dBFS active RMS
            out = _filter(raw * norm, sr, voice).astype(np.float32)
            del raw
            out *= np.float32(10 ** (voice.gain_db / 20))
            out *= automation
            stems[vname] = out
            mix += out
            if voice.send > 0:
                send += out * np.float32(voice.send)
        if np.any(send):
            wet = synth.reverb(
                send,
                sr,
                np.random.default_rng(cfg.seed + 21),
                t60=prod.reverb_t60,
                predelay=0.03,
                damping_hz=7000,
                mix=1.0,
            ).astype(np.float32)
            stems["reverb"] = wet
            mix += wet
            del wet
        del send
        wav = out_dir / f"{stem}{suffix}.wav"
        headroom = 0.0
        for _ in range(4):  # AAC encoding adds intersample overs: re-master with more headroom if needed
            master, loud = master_chain(mix.astype(np.float64), sr, prod, headroom)
            sf.write(wav, master, sr, subtype="PCM_24")
            m4a = _encode_m4a(wav)
            if not m4a:
                break
            tp_m4a = true_peak_db(_decode(m4a, sr, n))
            loud["m4a_true_peak_dbtp"] = round(tp_m4a, 2)
            if tp_m4a <= prod.true_peak_db:
                break
            headroom += tp_m4a - prod.true_peak_db + 0.1
        paths[f"master_{tuning}_wav"] = str(wav)
        if m4a:
            paths[f"master_{tuning}_m4a"] = str(m4a)
        # one shared gain for all stems (they sum to the pre-master mix), chosen so that neither the
        # sum nor any single stem exceeds the stem ceiling
        peak = max([float(np.max(np.abs(mix)))] + [float(np.max(np.abs(a))) for a in stems.values()])
        shared = stem_ceiling / peak if peak > 0 else 1.0
        stem_dir = out_dir / "stems"
        stem_stats = {}
        for k in list(stems):
            a = stems.pop(k)
            a *= np.float32(shared)
            if tuning == tunings[0]:
                stem_dir.mkdir(exist_ok=True)
                p = stem_dir / f"{stem}_{k}.{stem_format}"
                sf.write(p, a, sr, subtype="PCM_24", format=stem_format.upper())
                paths[f"stem_{k}"] = str(p)
            lu = integrated_lufs(a, sr)
            stem_stats[k] = {
                "lufs_at_stem_gain": round(lu, 1) if np.isfinite(lu) else None,
                "peak_dbfs": round(float(20 * np.log10(np.max(np.abs(a)) + 1e-12)), 2),
            } | _band_report(a, sr)
            del a
        del mix
        sections = {}
        for nme, a, b in section_spans(cfg):
            seg = master[int(a * sr) : int(b * sr)]
            lu = integrated_lufs(seg, sr)
            sections[nme] = round(lu, 1) if np.isfinite(lu) else None
        reports[tuning] = {"master": loud, "master_spectrum": _band_report(master, sr), "section_lufs": sections}
        reports[tuning]["stems"] = stem_stats
    return reports


def _encode_m4a(wav: Path) -> Path | None:
    if shutil.which("ffmpeg") is None:
        log.warning("ffmpeg not found; skipping .m4a")
        return None
    m4a = wav.with_suffix(".m4a")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", "aac", "-b:a", "256k", str(m4a)], check=True)
    return m4a


def _decode(path: Path, sr: int, n: int) -> Audio:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)[:n]
