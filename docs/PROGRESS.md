# Progress log & backlog

This file drives the autonomous 5-minute improvement loop. Keep the backlog ranked.

## Status
- v0.1.0: math core (zeros, explicit formula), engine, *Critical Strip* score, literal
  sonification, MIDI/JSON/plots, CLI, 42 tests, CI.

## Backlog (highest value first)
Outreach assets (plan: (private link) — Build phase 1–20 Dec 2026):
O2b. Clips: burn-in hook caption ("Add the zeros of ζ one by one…") + end card with repo/handle once the release name is decided.
O5. Video: use the empty lower third in 9:16 (e.g. the zero 'chord' as bars at γ_k).
O3. Interactive web demo: slider adds zeros, Web Audio plays the bar (static page, no backend).
O4. LICENSE (MIT code) once the user decides on audio licence (CC BY 4.0 recommended for clips/stems).
review (docs/reviews/review_review3_raw.log), fix first:
V1. Short clips → zero frames (int(duration*fps)). Validate fps/range before analysis; ceil frames; test sub-frame + non-integral counts.
V5. ffmpeg early exit → BrokenPipeError escapes; cleanup skips wait()/plt.close. Popen context manager + outer finally → RuntimeError.
V3. Decimal loop lengths: floor(u/loop) vs mod(u,loop) disagree at boundaries → wrap inside a segment. One shared cycle computation + test.
V2. Video for descending sweeps highlights unplayed side; sliding window direction.
V6. Video curve cache: key on exact (n, lo, hi); validate clip before full analysis; memory-budget chunking.
review findings (docs/reviews/review_2026-11-27_raw.log), fix in order:
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
- 2026-11-27 tick 4: O1+O2 done: `zeta-music video` (matplotlib→ffmpeg pipe, 16:9/9:16/1:1, --start/--end) + `make video clips`. Full 16:9 video (3:32, 11 MB) and 5 vertical clips (36–60 s). analyse() split out of render(). 55 tests.
- 2026-11-27 tick 5: fixed review C6: Timeline carries explicit `segment` ids (section starts + loop restarts); detection and video use them. Descending sweeps now work (regression test: 29→2 in order). Shipped piece's events identical. 56 tests.
- 2026-11-27 tick 6: fixed review C10: notes normalised to unit peak (level = salience), plucks+bells share one gain, bell_db now relative (-4 dB). Measured in mix: primes -4.2 dBFS vs prime powers -7.5 dBFS onset (median, N>=21). All proposals, video and clips re-rendered. 57 tests.
- 2026-11-27 tick 7: fixed review V4: events gated on the section's configured pluck_gain as well as the smoothed envelope (reproduced 2 leaked notes before the fix). Shipped scores unchanged (256 events each). 58 tests.
