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
V2. Video for descending sweeps highlights unplayed side; sliding window direction.
V6. Video curve cache: key on exact (n, lo, hi); validate clip before full analysis; memory-budget chunking.
review findings (docs/reviews/review_2026-11-27_raw.log), fix in order:
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
- 2026-11-27 tick 8: fixed review V1+V5 (same function): clip validated before analysis, fps>0, ceil frame count, output trimmed with -t; Popen context manager + stderr capture, BrokenPipe → RuntimeError with exit code/stderr, figure always closed. ffprobe-based tests (streams, frame counts 1/5/7, duration) + failing-encoder test. 66 tests. Existing clips unaffected (integral lengths).
- 2026-11-27 tick 9: fixed review V3: loop phase, bar index and zero step now come from one division (q = u/loop); test over loops 0.1/0.3/0.7/1.1 (old code failed 2 of 4). Shipped scores (integer loops) unaffected. 70 tests. review of ticks 6–8 running.
- 2026-11-27 tick 9b: acted on review (docs/reviews/review_review4_raw.log): video keeps partial last frame (no output -t; 1.201 s@5fps → 7 frames) and µs timestamp precision; notes mixed without stem normalisation via mix_notes() (−inf mutes cleanly, bell_db honoured); mute = configured gain 0 only (quiet sections keep notes); mix-stage tests. Balance kept (bell −4 dB, review agreed). Mix ~1.5 dB quieter, same shape; prime/power gap 3.7 dB. All media re-rendered. 74 tests.
- 2026-11-27 tick 10: fixed review C9: full score validation at load time (sweep/taper literals, finite numbers, non-negative zero counts/steps, loop>0, gains>=0, sample_rate>=8000, base/max freqs vs Nyquist, mix ranges, -inf mutes allowed, missing keys, invalid TOML); every error names its TOML location e.g. `sections[2] ('III. Further out'): sweep must be ...`. 13 new tests (87). Shipped scores validate; no audio change.
- 2026-11-27 tick 11: fixed review C3: two-pass drone (no retained envelopes; memory flat in #zeros), stems summed in place one at a time, salience chunk sized to ~16 MB/temporary, reverb blended per channel in place (oaconvolve tried: worse, reverted). Peak RSS 2.38 GB → 1.49 GB (−37%), output identical within 1 LSB (24-bit). Remaining peak = reverb FFT + master filtfilt on the full 208 s; fine for now.
- 2026-11-27 tick 12: fixed review C7: KS loop gain divides out |H(w0)|; notes whose required gain would exceed 0.9999 are synthesised at 2/4/8x and decimated (resample_poly). Measured t60 now 2.50 s at 98–1568 Hz (was 0.33 s at 1568 Hz), tuning 0.0 cents; decay + tuning tests to 2093 Hz. All media re-rendered (movement III high notes now ring). 94 tests.
- 2026-11-27 tick 12b: acted on review (docs/reviews/review_review5_raw.log): quiet sections (gain 0.01) keep notes; degenerate reverb returns dry instead of NaN + reverb_t60>=0.05; frequency validation relaxed (fundamentals < 0.45 sr; partials/notes above are dropped at render with a warning — 8 kHz scores playable); sections/loops must span >= 2 control frames; seed validated; mix_notes accumulates in place (peak RSS 1.49 → 1.37 GB); chunk floor 16; video test verifies clip audio comes from the requested interval. Shipped audio unchanged. 101 tests.
