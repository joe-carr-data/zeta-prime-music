# Progress log & backlog

This file drives the autonomous 5-minute improvement loop. Keep the backlog ranked.

## Status
- v0.1.0: math core (zeros, explicit formula), engine, *Critical Strip* score, literal
  sonification, MIDI/JSON/plots, CLI, 42 tests, CI.

## Backlog (highest value first)
From review (holistic, docs/reviews/review_review7_raw.log):
M1. Musical variant to audition as proposal F ("A, revised"), not replacing A: (a) reverse movement V's sweep (ends 3 → 2 at 148.6/95 Hz instead of a 343.9 Hz ghost); (b) movement IV as call and response: first 500-zero bar breath-only (pluck_gain 0), second articulated; (c) optional 16 s cut in II (drop the 89 and 144 bars).
R1. Public release (needs user decisions): LICENSE (MIT code; audio licence open), CONTRIBUTING.md, CHANGELOG.md, v0.1.0 tag, single-source version.
Outreach assets (plan: (private link) — Build phase 1–20 Dec 2026):
O2b. Clips: burn-in hook caption ("Add the zeros of ζ one by one…") + end card with repo/handle once the release name is decided.
O5. Video: use the empty lower third in 9:16 (e.g. the zero 'chord' as bars at γ_k).
P1. KS at low sr: 8x cap → 1568 Hz pluck t60 0.79 s instead of 2.5 at 8 kHz . Define achievable decay range + test.
O3b. Web demo follow-ups: tremolo per zero, a 'show waves' toggle (individual cos(γ ln x) traces), share-friendly #N hash.
O4. LICENSE (MIT code) once the user decides on audio licence (CC BY 4.0 recommended for clips/stems).
review (docs/reviews/review_review3_raw.log), fix first:
review findings (docs/reviews/review_2026-11-27_raw.log), fix in order:
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
- 2026-11-27 tick 13: O3 done: interactive demo 'Hear the Primes' (web/hear-the-primes.src.html → scripts/build_web.py → output/web/, `make web`), published privately at (private link) Slider 1–200 zeros, live graph-paper plot with labelled peaks, Play bar (drone + KS plucks + FM bells via Web Audio), Build-up through Fibonacci counts. JS maths verified against Python (identical peaks at N=1/13/200). 102 tests.
- 2026-11-27 tick 14: fixed review C8: MIDI notes get a channel free the longest (by release tick); with all 15 busy the soonest-ending voice is stolen and its note-off pulled to the new onset — no shared bends, no stale note-offs. Tests: 40 overlapping notes never share a sounding channel; sparse notes keep full length. 104 tests. review (pluck oversampling + web demo) running.
- 2026-11-27 tick 14b: acted on review web findings: per-playback session bus (Stop/replay fade + cancel all scheduled notes), persistent 120-oscillator drone bank with gain ramps (no churn), slider mid-bar cancels future notes and reschedules from the playhead, lookahead bar scheduler on the audio clock (no drift), resume/interruption handling with transport tokens, cached cos table + rAF-coalesced input (2.4 ms/update), KS onset ramp, incremental zero list, screen-reader peak list, lang. Republished. Node parity test vs Python (N=1/13/55/200). Pluck findings → P1/P2. 108 tests.
- 2026-11-27 tick 15: P2 (KS brightness at oversampling boundaries): measured; factor now chosen from worst-case fractional delay → monotonic in pitch (was flickering 1↔2↔1 every few Hz, 60+ switch points 778–2200 Hz → 3); excitation filter cutoff fixed in output-rate Hz. Remaining ~1.5x centroid step at 778/1227/1929 Hz is inherent to holding t60 with a 3-tap loop (static post-lowpass tried: cannot match sustain) — documented; affects ~15 notes (x≥181, movement III) and coincides with the octave-3 register jump. Media re-rendered. 109 tests.
- 2026-11-27 tick 16: review C5: documented that S(n)→Λ(n)/log n is a fixed-n limit (Gonek uniform Landau error ~ n log(nT)/T); measured medians with 500 zeros 0.99/0.92/0.81/0.74 over x 2–30/30–100/100–180/180–260, written into salience_curve docstring + COMPOSITION.md table and pinned by a test. Kept as musically honest (unresolvable primes are quieter). Ordinate-space window not adopted (index taper is what the music uses; documented). 113 tests.
- 2026-11-27 tick 17: fixed review V2+V6: video window leads in the direction of travel and is clamped to the section; traced part follows direction; curve cache keyed on exact (N, lo, hi) so identical bars share one curve (clip validation + chunk budget were done in ticks 8/12). Ascending output unchanged. 115 tests. All review code findings (reviews 1–6) now closed or documented; remaining backlog: P1 (8 kHz decay range), user decisions (O2b captions, O4 licence), optional extras (O3b, O5).
- 2026-11-27 tick 17b: review (holistic): wheel verified (zeros.txt, py.typed, entry point). Fixed: Makefile builds every deliverable from a clean clone (explicit WAV rules, .PHONY incl. web, proposals target with A–E names, encode script); CI uses UV_PYTHON for the whole job, `uv sync --locked`, asserts the interpreter, installs ffmpeg + node so video/parity tests run, plus a wheel-install smoke job; MIDI title transliterated to latin-1 (ζ → zeta) instead of crashing after the WAV; literal -n 0 / explain -n 1 give clear errors; graphic score plots bells at sounding pitch; README commands copyable (uv run, real literal modes, plot extra, ffmpeg); COMPOSITION.md pole/breath rows corrected. Musical ideas → M1, release items → R1. 117 tests.
