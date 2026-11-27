# Progress log & backlog

This file drives the autonomous 5-minute improvement loop. Keep the backlog ranked.

## Status
- v0.1.0: math core (zeros, explicit formula), engine, *Critical Strip* score, literal
  sonification, MIDI/JSON/plots, CLI, 42 tests, CI.

## Backlog (highest value first)
Outreach assets (plan: (private link) — Build phase 1–20 Dec 2026):
O1. Visualiser video: animated ψ'_N(x) spikes + zero count synced to audio, 16:9 and 9:16 (matplotlib/ffmpeg), `zeta-music video`.
O2. Five 30–60 s vertical clips cut from A/B (the bar snapping into tune is the hook), captions burned in.
O3. Interactive web demo: slider adds zeros, Web Audio plays the bar (static page, no backend).
O4. LICENSE (MIT code) once the user decides on audio licence (CC BY 4.0 recommended for clips/stems).
review findings (docs/reviews/review_2026-11-27_raw.log), fix in order:
C6. detect_events treats any negative diff(x) as loop reset → descending sweeps lose notes. Carry explicit boundaries.
C10. Stem normalisation cancels 1/k bell loudness cue. Calibrate voices at unit salience, shared gain.
C3. Memory: 500 control envelopes 1.66 GB + 5 float64 stems. Normalise first, synthesise per-partial without retaining rows, mix sequentially.
C9. Config validation (sweep literal, finite values, sr-dependent cutoffs).
C7. KS decay calibration at high pitch (loop filter magnitude at f0).
C8. MIDI channel allocation by release tick.
C5. Document fixed-n Landau limit; window in ordinate space; test far-end salience (S(251)=0.71).
2. Perceptual check of the render: spectral/loudness analysis per movement; check drone is not
   harsh at high partials (consider spectral tilt / lower `drone_max_hz`).
3. Movement III melodic contour: folded pitch makes mechanical rising scales under exp sweep —
   consider register by prime-gap or by `k ln p` mod octave.
4. ~~Performance~~ DONE: drone synthesises only active spans, 69 s → 23 s (bit-identical).
5. Literal "log-mode" interlude spliced into the piece (chord of the zeros as a struck bell).
6. Dirichlet L-function voices (mod 4: primes ≡1 vs ≡3) as two stereo instruments (Chebyshev bias).
7. Stem export (drone/plucks/bells/breath) for mixing in a DAW.
8. Loudness normalisation to −14 LUFS (pyloudnorm) for streaming.
9. Integrate findings from a literature survey research report (docs/research/) once available.

## Log
- 2026-11-27: initial build; first render 204 s, 182 primes / 46 prime powers / 29 ghosts.
- 2026-11-27: drone render restricted to each zero's active span: 3x faster, identical output.
- 2026-11-27 tick 1: fixed review C2 (octave jump at powers of 2): pitch/pan anchored to nearest integer, detuned by x/n. Prime 2 now 95.5–98.3 Hz (was 98/196). Regression test added.
- 2026-11-27 tick 2: fixed review C1: salience uses only the zeros' oscillatory term, I_w floored at one zero, taper width floored at N=1 (previously the gauss taper zeroed the fading-in first zero). Intro breath layer now fades in with the first zero. Regression test added (44 tests).
- 2026-11-27 tick 3: fixed review C4 (spike_density layout bug: flat C buffer + reshape; chunk>0 validated). review requested on ticks 1–3.
- 2026-11-27 tick 3b: acted on review (docs/reviews/review_review2_raw.log): salience floor = one *tapered* zero (first bar no longer attenuated, N=1 full scale for all tapers); pan regression test; negative-stride + chunk=-1 tests; COMPOSITION.md pitch formula updated.
