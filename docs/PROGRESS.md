# Status, backlog and development log

## Status
- v0.1.0 (unreleased): maths core (zeros, explicit formula), composition engine, the score
  *Critical Strip* and proposals A–F, literal sonifications, MIDI/JSON/plots, visualiser video
  and clips, interactive web demo, CLI, 144 tests, CI.

## Open backlog (highest value first)
1. **Release decisions:** which proposal is canonical (A or F); licence for code (MIT suggested)
   and for audio (CC BY 4.0 suggested for clips/stems); then CONTRIBUTING.md, CHANGELOG.md,
   a v0.1.0 tag and a single-source version number.
2. **Clips:** burned-in hook caption ("Add the zeros of ζ one by one…") and an end card with the
   repository / release name.
3. **Optional polish:** per-zero tremolo in the demo drone; use the empty lower third of the 9:16
   video (the zero "chord" as bars at γ_k).
4. **Musical ideas:** register in movement III by prime gap or by `k ln p` mod octave; splice the
   literal "chord of the zeros" in as an interlude; Dirichlet L-function voices (primes ≡ 1 vs 3
   mod 4, Chebyshev's bias) as two stereo instruments; stem export for mixing; loudness
   normalisation to −14 LUFS for streaming; findings from the research brief
   (`docs/RESEARCH_BRIEF.md`) once a report exists in `docs/research/`.

## Development log (2026-11-27)
- Initial build: first render 204 s, 182 primes / 46 prime powers / 29 ghosts. Drone rendered
  only over each zero's active span: 3× faster, identical output.
- Pitch and pan anchored to the nearest integer and detuned by x/n: no more octave jumps as a
  peak converges on a power of two.
- Salience uses only the zeros' oscillatory term, with the bandwidth floored at one tapered zero
  and the taper never narrower than one zero: bounded and full-scale while the first zero fades in.
- `spike_density` independent of array memory layout; `chunk` validated.
- Visualiser video (`zeta-music video`, 16:9 / 9:16 / 1:1, `--start/--end`) and five vertical
  clips; `analyse()` split out of `render()`.
- Explicit bar/sweep segment ids in the timeline: descending sweeps keep their notes.
- Notes normalised to unit peak so level = salience; plucks and bells mixed with one shared gain
  (bells −4 dB): prime powers sound 1/k quieter than primes.
- Muted sections never trigger notes; quiet (non-zero gain) sections keep theirs.
- Video robustness: partial last frames kept, clip validated before analysis, encoder failures
  reported cleanly; clip audio verified against the requested interval.
- Loop phase, bar index and zero step computed from one division (decimal loop lengths wrap at
  bar boundaries).
- Score validation at load time with errors that name the TOML location.
- Render memory 2.38 GB → 1.37 GB with identical output (two-pass drone, in-place stem and note
  mixing, per-channel reverb, budgeted salience chunks).
- Karplus–Strong decay calibrated at every pitch (loop-loss compensation + oversampling up to a
  384 kHz internal rate); oversampling factor monotonic in pitch; excitation filter fixed in
  output-rate Hz. A ~1.5× brightness step remains at 778 / 1227 / 1929 Hz (inherent to holding t60
  with a 3-tap loop; documented).
- MIDI: channels allocated by release time with voice stealing; non-Latin titles transliterated.
- Salience accuracy versus distance documented and pinned by tests (fixed-n Landau limit).
- Interactive web demo "Hear the Primes": slider 1–200 zeros, playable bar, build-up, waves
  toggle, shareable `#zeros-N` link; JavaScript maths checked against the Python engine.
- Release engineering: every deliverable builds from a clean clone (`make all`); CI on Python
  3.12/3.13 with ffmpeg and Node plus a wheel-install smoke test.
- Proposal F (*Critical Strip (revised)*): shorter movement II, call-and-response movement IV,
  reversed movement V ending on 3 → 2.
