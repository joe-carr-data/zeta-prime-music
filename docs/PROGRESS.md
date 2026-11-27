# Progress log & backlog

This file drives the autonomous 5-minute improvement loop. Keep the backlog ranked.

## Status
- v0.1.0: math core (zeros, explicit formula), engine, *Critical Strip* score, literal
  sonification, MIDI/JSON/plots, CLI, 42 tests, CI.

## Backlog (highest value first)
1. review review of math + engine; act on findings.
2. Perceptual check of the render: spectral/loudness analysis per movement; check drone is not
   harsh at high partials (consider spectral tilt / lower `drone_max_hz`).
3. Movement III melodic contour: folded pitch makes mechanical rising scales under exp sweep —
   consider register by prime-gap or by `k ln p` mod octave.
4. Performance: drone render dominates (~60 s). Vectorise in blocks / float32 / FFT-based
   additive synthesis.
5. Literal "log-mode" interlude spliced into the piece (chord of the zeros as a struck bell).
6. Dirichlet L-function voices (mod 4: primes ≡1 vs ≡3) as two stereo instruments (Chebyshev bias).
7. Stem export (drone/plucks/bells/breath) for mixing in a DAW.
8. Loudness normalisation to −14 LUFS (pyloudnorm) for streaming.
9. Integrate findings from a literature survey research report (docs/research/) once available.

## Log
- 2026-11-27: initial build; first render 204 s, 182 primes / 46 prime powers / 29 ghosts.
