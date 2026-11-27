# zeta-music — the music of the primes

Compositions generated from the nontrivial zeros of the Riemann zeta function.

Each zero ρ = ½ + iγ adds one oscillation x^{-1/2} cos(γ ln x) to the explicit formula for the
primes. Add enough of them and the sum spikes at 2, 3, 5, 7, 11… with smaller "overtones" at
4, 8, 9, 16 (the prime powers). This repo turns that interference pattern into music: the
**zeros are the drone**, the **primes are the melody**, and the piece *Critical Strip* lets you hear
the primes come into tune as zeros are added one Fibonacci number at a time.

Inspired by *From First Principles* ep. 69 — see [docs/VIDEO_ANALYSIS.md](docs/VIDEO_ANALYSIS.md).

## Quick start

```bash
uv sync                      # Python ≥ 3.12
make render                  # → output/critical_strip.{wav,mid,events.json,score.png}
make literal                 # raw sonifications: the zeros' chord, and the prime clicks
make explain                 # figure reproducing the video's argument
make test lint
```

CLI:

```bash
zeta-music render compositions/critical_strip.toml -o output
zeta-music literal {log|linear} -n 200 -d 10 -o output/x.wav
zeta-music explain -n 200 --xmax 30
zeta-music zeros 10
```

## Layout

```
src/zeta_music/
  zeros.py        first 500 zeros bundled (mpmath), more computed + cached on demand
  explicit.py     ψ(x), ψ'(x) explicit formulas, prime powers, von Mangoldt, spectral tapers
  composition.py  timeline → salience curve → note events → drone/plucks/bells/breath → mix
  synth.py        Karplus–Strong, FM bell, convolution reverb, mastering
  midi.py         MIDI export with microtonal pitch bend
  literal.py      direct sonification of the sums
  plots.py        explainer figure + graphic score
  config.py       typed TOML score format
compositions/     scores (TOML)
docs/             video analysis, composition notes, research prompt, progress/backlog
tests/            pytest suite (math is tested against known values)
```

## Writing your own piece

A score is a list of sections, each sweeping the number line `x` while a number of zeros is
switched on. See [compositions/critical_strip.toml](compositions/critical_strip.toml) and
[docs/COMPOSITION.md](docs/COMPOSITION.md) for every mapping and its mathematical justification.
