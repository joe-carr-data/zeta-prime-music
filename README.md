# Zeta Prime Music

![Each zero of the Riemann zeta function is a wave; add 200 of them and the primes appear](docs/media/hero.gif)

**▶ Listen to *The Sound of the Primes*:** https://joe-carr-data.github.io/zeta-prime-music/#listen — one bar of the number line played by piano, vibraphone, bass and drums while the zeros of ζ are added, until the band locks onto the primes.

Compositions generated from the nontrivial zeros of the Riemann zeta function.

Each zero ρ = ½ + iγ adds one oscillation x^{-1/2} cos(γ ln x) to the explicit formula for the
primes. Add enough of them and the sum spikes at 2, 3, 5, 7, 11… with smaller "overtones" at
4, 8, 9, 16 (the prime powers). This repo turns that interference pattern into music: the
**zeros are the drone**, the **primes are the melody**, and the piece *Critical Strip* lets you hear
the primes come into tune as zeros are added one Fibonacci number at a time.

Inspired by [*From First Principles* ep. 69](https://www.youtube.com/watch?v=zSGBxRjzyb8) — see [docs/VIDEO_ANALYSIS.md](docs/VIDEO_ANALYSIS.md).

On the November 2026 proof of the Riemann Hypothesis by Levent Alpöge: this music does not use or depend on it.
It is built from numerically computed zeros and the explicit formula, and would sound the same either way.

**Musicians:** how the piece is built (tuning, harmony, rhythm, dynamics, form), with the
maths behind every note: [docs/FOR_MUSICIANS.md](docs/FOR_MUSICIANS.md).

## Quick start

```bash
uv sync                      # Python ≥ 3.12
make render                  # → output/critical_strip.{wav,mid,events.json,score.png}
make proposals               # → output/proposals/A–E (.wav + .m4a)
make video clips             # visualiser video + five vertical clips (needs ffmpeg)
make web                     # interactive demo → output/web/hear-the-primes.html
make explain                 # figure reproducing the video's argument
make hero                    # README animation → docs/media/hero.gif (needs ffmpeg)
make produce                 # radio edit → output/commercial (needs fluidsynth + a GM SoundFont)
make all                     # everything above from a clean clone, after lint + tests
make test lint
```

CLI (after `uv sync`; plots and video need the `plot` extra — `uv sync --extra plot` or
`pip install '.[plot]'` — and video needs ffmpeg on PATH):

```bash
uv run zeta-music render compositions/critical_strip.toml -o output
uv run zeta-music literal log -n 200 -d 10 -o output/zeros_chord.wav
uv run zeta-music literal linear -n 200 -d 10 -o output/prime_clicks.wav
uv run zeta-music explain -n 200 --xmax 30
uv run zeta-music video compositions/critical_strip.toml --audio output/critical_strip.wav --aspect 9:16 --start 16 --end 64
uv run zeta-music zeros 10
uv run --extra produce zeta-music produce compositions/commercial/critical_strip_radio.toml --soundfont GeneralUser-GS.sf2
uv run --extra produce zeta-music produce-preset --plugin /Library/Audio/Plug-Ins/VST3/X.vst3 --out x.state
```

## Layout

```
src/zeta_music/
  zeros.py        first 500 zeros bundled (mpmath), more computed + cached on demand
  explicit.py     ψ(x), ψ'(x) explicit formulas, prime powers, von Mangoldt, spectral tapers
  composition.py  timeline → salience curve → note events → drone/plucks/bells/breath → mix
  produce.py      produced version: tempo map, just/tempered MIDI, SoundFont/plugin instruments, mix, master
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

## Licence

Code: [MIT](LICENSE). Music, video, animation and figures: [CC BY 4.0](LICENSE-MEDIA.md) —
credit "Zeta Prime Music" by Joe Carr.
