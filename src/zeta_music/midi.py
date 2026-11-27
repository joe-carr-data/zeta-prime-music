"""MIDI export of detected events with microtonal pitch bend (one channel per voice)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import mido
import numpy as np

if TYPE_CHECKING:
    from .composition import Event
    from .config import CompositionConfig

__all__ = ["allocate_channels", "freq_to_midi", "write_midi"]

PPQ = 960
BPM = 60.0  # 1 beat = 1 second: MIDI time equals audio time
BEND_RANGE = 2.0  # semitones
# rotate over channels so each sounding note can carry its own bend (skip drums ch 9)
CHANNELS = [c for c in range(16) if c != 9]


def freq_to_midi(freq: float) -> tuple[int, int]:
    """Return (note, pitchwheel) for a frequency, bend in [-8192, 8191] for ±BEND_RANGE."""
    m = 69.0 + 12.0 * np.log2(freq / 440.0)
    note = int(np.clip(round(m), 0, 127))
    bend = int(np.clip(round((m - note) / BEND_RANGE * 8192), -8192, 8191))
    return note, bend


PROGRAMS = {"prime": 24, "prime_power": 14, "ghost": 45}  # nylon gtr, tubular bells, pizz.


def allocate_channels(events: list[Event]) -> list[tuple[int, int, int, int, int, int, int]]:
    """Give every note its own channel for as long as it sounds (so its pitch bend is private).

    Returns ``(channel, on_tick, off_tick, note, bend, velocity, program)`` per event. A note goes
    to the channel that has been free the longest. With all 15 busy, the voice that would end
    soonest is stolen: its note-off is pulled forward to the new onset, so no stale note-off can
    cut the new note and no bend retunes a sounding note.
    """
    free_at = dict.fromkeys(CHANNELS, 0)
    owner: dict[int, int] = {}  # channel -> index into notes
    notes: list[list[int]] = []
    for e in sorted(events, key=lambda ev: ev.time):
        note, bend = freq_to_midi(e.freq * (2.0 if e.kind == "prime_power" else 1.0))
        vel = int(np.clip(30 + 90 * min(e.salience, 1.0), 1, 127))
        on = round(e.time * PPQ * BPM / 60.0)
        off = on + int((1.5 if e.kind != "ghost" else 0.4) * PPQ)
        idle = [c for c in CHANNELS if free_at[c] <= on]
        if idle:
            ch = min(idle, key=lambda c: free_at[c])
        else:  # voice stealing
            ch = min(CHANNELS, key=lambda c: free_at[c])
            notes[owner[ch]][2] = on
        owner[ch] = len(notes)
        free_at[ch] = off
        notes.append([ch, on, off, note, bend, vel, PROGRAMS[e.kind]])
    return [tuple(n) for n in notes]  # type: ignore[misc]


def midi_text(text: str) -> str:
    """MIDI meta text is latin-1 in mido; keep what fits, transliterate the rest (ζ -> 'zeta')."""
    import unicodedata

    greek = {"ζ": "zeta", "ρ": "rho", "γ": "gamma", "ψ": "psi", "π": "pi", "Λ": "Lambda", "σ": "sigma"}
    out = unicodedata.normalize("NFKD", "".join(greek.get(ch, ch) for ch in text))
    return out.encode("latin-1", "ignore").decode("latin-1").strip() or "untitled"


def write_midi(events: list[Event], path: Path, cfg: CompositionConfig) -> None:
    mid = mido.MidiFile(ticks_per_beat=PPQ)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name=midi_text(cfg.title), time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))
    for ch in CHANNELS:  # RPN 0: pitch bend range
        for ctl, val in ((101, 0), (100, 0), (6, int(BEND_RANGE)), (38, 0)):
            track.append(mido.Message("control_change", channel=ch, control=ctl, value=val, time=0))

    msgs: list[tuple[int, int, mido.Message]] = []  # (tick, order, msg)
    for ch, on, off, note, bend, vel, program in allocate_channels(events):
        msgs.append((on, 0, mido.Message("program_change", channel=ch, program=program)))
        msgs.append((on, 1, mido.Message("pitchwheel", channel=ch, pitch=bend)))
        msgs.append((on, 2, mido.Message("note_on", channel=ch, note=note, velocity=vel)))
        msgs.append((off, -1, mido.Message("note_off", channel=ch, note=note, velocity=0)))
    msgs.sort(key=lambda m: (m[0], m[1]))
    last = 0
    for tick, _, msg in msgs:
        track.append(msg.copy(time=tick - last))
        last = tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    mid.save(path)
