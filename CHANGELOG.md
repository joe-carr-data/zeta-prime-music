# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-11-27

First public release.

### Music
- *Critical Strip*, a five-movement piece generated from the explicit formula: zeros as an
  inharmonic drone, prime spikes as plucked strings, prime powers as bells, unresolved peaks as
  ghost notes; movement II replays one bar while zeros are added along the Fibonacci numbers.
- Proposals B–F: *Prime Pulse*, *Deep Strip*, two literal sonifications and
  *Critical Strip (revised)*.

### Engine
- Explicit-formula core: 500 bundled zeros (more computed and cached on demand), ψ(x) and ψ′(x)
  with spectral tapers, prime powers and von Mangoldt weights.
- Composition engine with normalised salience (1 at primes, 1/k at prime powers), just-intonation
  pitch mapping, explicit bar/sweep segments, calibrated Karplus–Strong strings, FM bells,
  convolution reverb and mastering; 24-bit WAV, event JSON and microtonal MIDI export.
- Score format (TOML) validated at load time, with errors naming the offending field.

### Media and outreach
- Visualiser video and vertical clips (`zeta-music video`), README hero animation
  (`zeta-music animate`), interactive web instrument and a GitHub Pages site with a guide for
  musicians.

### Quality
- 147 tests, ruff, CI on Python 3.12 and 3.13 with a wheel-install smoke test; every deliverable
  builds from a clean clone with `make all`.

[0.1.0]: https://github.com/joe-carr-data/zeta-prime-music/releases/tag/v0.1.0
