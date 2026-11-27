# Status, backlog and development log

## Status
- v0.1.0: public at github.com/joe-carr-data/zeta-prime-music, site on GitHub Pages; MIT code, CC BY 4.0 media; maths core (zeros, explicit formula), composition engine, the score
  *Critical Strip* and proposals A–F, literal sonifications, MIDI/JSON/plots, visualiser video
  and clips, interactive web demo, CLI, tests, CI.

## Open backlog (highest value first)
1. **Release:** tag v0.1.0 and publish a GitHub release with the two audio tracks attached
   (CHANGELOG, CONTRIBUTING, licences and single-source version are in place). Canonical version:
   *Critical Strip* (A), with *Critical Strip (revised)* as the alternative.
2. **Optional polish:** per-zero tremolo in the demo drone; use the empty lower third of the 9:16
   video (the zero "chord" as bars at γ_k).
3. **Musical ideas:** register in movement III by prime gap or by `k ln p` mod octave; splice the
   literal "chord of the zeros" in as an interlude; Dirichlet L-function voices (primes ≡ 1 vs 3
   mod 4, Chebyshev's bias) as two stereo instruments; loudness
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
- Public-release housekeeping: LICENSE (MIT) and LICENSE-MEDIA.md (CC BY 4.0), CHANGELOG, CONTRIBUTING, version single-sourced from pyproject (`zeta-music --version`).
- Clips: `zeta-music video --caption … --end-card` (opening caption over the first 4 s, title card with the site address over the last 2.5 s); `make clips` captions all five.
- Site and docs review fixes: instrument fits phone screens; table headings, meta text and legend meet 4.5:1 contrast; hero animation is a pausable video that respects reduced motion; movement timelines stack on phones; bell levels stated relative to a prime (−10 / −13.5 / −16 dB); register rule and first-bar pitches corrected; revised track duration 3:12; absolute share image; captions are literal text and never cover the axis labels; hatchling ≥ 1.26 for licence metadata.
- Stem export: `zeta-music render --stems` writes five dry stereo stems (drone, plucks, bells, breath, pole) at mix balance with one shared gain, summing to the dry mix; the main mix is unchanged. Groundwork for a produced version with sampled or live instruments.
- Site: 60-second vertical clip beside the visualiser, a plain note that the music does not depend on the claimed proof of the Riemann Hypothesis announced in November 2026, and a direct credit link to From First Principles ep. 69 (site and README).
- Produced radio edit (`zeta-music produce`, `compositions/commercial/critical_strip_radio.toml`): 112.5 BPM 5/4 tempo map, just and tempered MIDI, per-voice SoundFont or plugin instruments with saved plugin states (`produce-preset`), FX chains, bus compression, −14 LUFS / −1 dBTP mastering, float32 in-place mixing; review fixes for silence, fades, plugin presets, MIDI ports, limiter ceiling, stem gain and validation; brighter mix with a lifted intro and an open tempered drone voicing.
- Native Instruments plugins driven from code (Massive, Raum, Replika, Solid Bus Comp, Guitar Rig 6, Kontakt 8 load and render; Kontakt instruments still need a sound chosen once by hand). Plugin instrument voices accept parameter values (`params`), so a synth patch can be written in the score. Scores: `critical_strip_radio_nifx.toml` (NI effects) and `critical_strip_radio_massive.toml` (plus a Massive pad drone).
- Proposal J (`critical_strip_radio_kontakt.toml`): primes on The Gentleman, bells on Toys - Rapman Vibraphone (Factory Selection 2 has no celesta or glockenspiel; the vibraphone sounds an octave above the key, so bells transpose −12), bass on Scarbee Rickenbacker Bass (keys below 35 are keyswitches and the library sounds an octave below the key, so bass transposes +12), pulse on Drum Lab "Smooth / RnB Ballad" (no brush kit; GM keys 36/37/49/70 all sound). Kontakt voices play tempered (Omni applies pitch bend to every note); states in `output/states/` (not committed), MIDI set to Omni. −14.0 LUFS, −1.3 dBTP. Offline Kontakt rendering is slow: render time grows faster than the length (Drum Lab: 14 s of audio in 39 s, 24 s in 144 s), and the full render took 45 min.
- The radio edit with sampled instruments becomes the main track, "The Sound of the Primes": featured on the site and in the README, a radio-edit section in both guides for musicians, and the media licence clarified (released mixes only; separate instrument stems are not distributed).
- Site and README: a note on the November 2026 announced proof of the Riemann Hypothesis ("this is what those zeros sound like").
- Wording: the proof is presented as announced/claimed and under examination, not as settled.
- Video for the produced radio edit: `zeta-music video` accepts a score with a `[produce]` table (labels follow the arrangement; note times identical to the produced events), `--title`, captions wrapped inside the frame; `make video-j` renders proposal J's full video and five vertical clips.
- Fast re-renders: per-voice cache of raw instrument audio (`output/cache/`, SHA-256 key of notes, tuning, instrument, plugin state bytes and parameters; atomic writes; `--no-cache`, `--clear-cache`, `zeta-music clear-cache`) and plugin voices rendered in parallel processes (`--jobs`). Proposal J: cold render 39 min (Drum Lab alone ~35 min), mix-only change 29 s.
- Render cache review fixes: `clear-cache` removes only files named by a cache key; the key adds the plugin build (Info.plist digest), pedalboard and FluidSynth versions and the render code. Measured on J: cold 39 min (Drum Lab alone ~35 min), mix-only re-render 29 s.
- Site and README introduction rewritten: "Nobody wrote the melody. It was hiding in the prime numbers.", a three-part section on the mystery, and a README with buttons, badges and a maths-to-music table.
- Site media: the visualiser and the one-minute clip are now *The Sound of the Primes* (`sound-of-the-primes.mp4`, 2:56, and `sound-of-the-primes-60s.mp4`, 64 s: 2 → 500 zeros, `make video-j` target `J_6_the_story.mp4`), web-encoded with H.264 CRF 28 and faststart; share image from the full video.
- *The Sound of the Primes* is now proposal J2 (`compositions/commercial/the_sound_of_the_primes.toml`): proposal J without bass, sub or drums, so every note comes from the zeros (their energy sat almost entirely below 100 Hz, inaudible on phone and laptop speakers). Piano, vibraphone and the Massive pad render in 3.3 min; −14.0 LUFS, −1.3 dBTP. Site audio, video, clip and posters re-rendered from it; `make video-j` builds from it.
- Review fixes before promotion: headline backed by the score ("we chose only the instruments, the key, the tempo and the form"), "every nontrivial zero", peaks described as sharpening rather than exact cancellation, γ > 0 in the formula, equal temperament stated for the main track, media licence limited to finished mixes (no samples, presets or plugin states), demo drone described as the first 120 zeros, `--clear-cache` after a sample-library update, audio players named, light-theme label contrast, sieve numbers kept on phones, share previews for every page, neutral wording in the CLI help and the video analysis.
