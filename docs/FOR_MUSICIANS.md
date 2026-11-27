# Zeta Prime Music for musicians

How *Critical Strip* is built, explained in terms of tuning, harmony, rhythm, dynamics and form,
with just enough of the mathematics to see where every note comes from. No note in the piece is
placed by hand: the composer's decisions are the mappings described below, and the mathematics
fills in the rest.

## 1. The idea in one paragraph

Riemann's explicit formula writes the primes as a sum of waves. Each nontrivial zero of the zeta
function, ρ = ½ + iγ, contributes one wave, cos(γ ln x), along the number line. One zero gives a
smooth wobble. Add a few hundred and the waves cancel almost everywhere, except at 2, 3, 4, 5, 7,
8, 9, 11, 13 … where they pile up into sharp spikes: the primes (tall) and the prime powers
(shorter). The piece turns that into music:

| In the maths | In the music |
|---|---|
| a zero γ | a sustained partial in the **drone** |
| a spike at a prime p | a **plucked string** |
| a spike at a prime power p^k | a softer **bell** |
| a spike that is not yet on an integer | an out-of-tune **ghost note** |
| the number of zeros used | how "in tune" the music is |
| moving along the number line | **time** |

The central gesture: the same bar is replayed while zeros are added. You hear wrong notes slide
into tune until the bar plays the primes exactly.

## 2. Two scales that meet: inharmonic drone, harmonic melody

The piece uses two pitch systems at once.

### 2.1 The drone: the zeros as a spectrum

Each zero becomes a sine partial at `f_k = 82.41 Hz × γ_k / γ_1`, so the first zero is E2 (the
lowest guitar string) and every other zero keeps its exact ratio to it:

| zero | γ | ratio to γ₁ | cents above E2 | frequency | nearest note |
|---|---|---|---|---|---|
| 1 | 14.135 | 1.000 | 0 | 82.4 Hz | E2 |
| 2 | 21.022 | 1.487 | 687 | 122.6 Hz | B2 −13¢ |
| 3 | 25.011 | 1.770 | 988 | 145.8 Hz | D3 −12¢ |
| 4 | 30.425 | 2.153 | 1327 | 177.4 Hz | F3 +27¢ |
| 5 | 32.935 | 2.330 | 1464 | 192.0 Hz | G3 −35¢ |
| 6 | 37.586 | 2.659 | 1693 | 219.1 Hz | A3 −7¢ |
| 7 | 40.919 | 2.895 | 1840 | 238.6 Hz | B♭3 +40¢ |
| 8 | 43.327 | 3.065 | 1939 | 252.6 Hz | B3 +39¢ |
| 9 | 48.005 | 3.396 | 2117 | 279.9 Hz | C♯4 +17¢ |
| 10 | 49.774 | 3.521 | 2179 | 290.2 Hz | D4 −21¢ |

These ratios are **not** a harmonic series. The zeros are not multiples of each other, so the
drone is inharmonic, like a bell or a gong rather than a string. That is why it sounds metallic.
Two facts shape its colour:

- **It gets denser as it rises.** Near the bottom the zeros are about 7.8 units of γ apart; near
  γ = 100 about 2.3; near γ = 400 about 1.5 (the average spacing is 2π / ln(γ/2π)). In the drone
  the low partials stand apart as a chord, and the high ones crowd into a shimmering cluster.
- **Zeros avoid each other.** Their spacings follow the same statistics as the energy levels of
  heavy atomic nuclei (the "GUE" law of random matrices): two zeros almost never sit very close
  together. Musically, the cluster has fewer very slow beats than a random cluster of the same
  density would.

An observation, not a design choice: the first six zeros land near **E, B, D, F, G, A**. That is
an E minor seventh (E–G–B–D) with an added 11th (A) and a flat 9th (F), the colour of the
Phrygian mode. Every zero gets a loudness of 1/|ρ| (the higher the zero, the quieter its partial),
the exact weight it has in the formula, so this low chord dominates what you hear.

Each partial also has a slow **tremolo**: its loudness follows its own wave cos(γ ln x) at the
current point x on the number line. Higher zeros pulse faster.

### 2.2 The melody: primes as harmonics

Every spike sits on a whole number n. The piece hears n as **the n-th harmonic of G2 (98 Hz)**,
folded down by octaves into one register: `pitch = 98 Hz × n / 2^⌊log₂ n⌋`, raised by a register
rule (one octave per factor 2^2.5 in n, at most three). So the primes become the prime-limit
intervals of just intonation:

| n | kind | interval above G | cents | heard as | level vs a prime |
|---|---|---|---|---|---|
| 2 | prime | octave (tonic) | 0 | G2 | 0 dB |
| 3 | prime | perfect fifth 3/2 | 702 | D3 +2¢ | 0 dB |
| 4 | 2² | octave | 0 | G3 (bell) | −10 dB |
| 5 | prime | major third 5/4 | 386 | B2 −14¢ | 0 dB |
| 7 | prime | harmonic seventh 7/4 | 969 | F4 −31¢ | 0 dB |
| 8 | 2³ | octave | 0 | G4 (bell) | −13.5 dB |
| 9 | 3² | major ninth 9/8 | 204 | A4 +4¢ (bell) | −10 dB |
| 11 | prime | undecimal tritone 11/8 | 551 | between C and C♯ (C♯4 −49¢) | 0 dB |
| 13 | prime | tridecimal neutral sixth 13/8 | 841 | between E♭ and E (E♭4 +41¢) | 0 dB |
| 16 | 2⁴ | octave | 0 | G4 (bell) | −16 dB |
| 17 | prime | 17/16, a small semitone | 105 | G♯3 +5¢ | 0 dB |
| 19 | prime | 19/16, a minor third | 298 | B♭3 −2¢ | 0 dB |
| 23 | prime | 23/16 | 628 | C♯4 +28¢ | 0 dB |
| 25 | 5² | augmented fifth 25/16 | 773 | E♭5 −27¢ (bell) | −10 dB |
| 27 | 3³ | Pythagorean major sixth 27/16 | 906 | E5 +6¢ (bell) | −13.5 dB |
| 29 | prime | 29/16 | 1030 | F4 +30¢ | 0 dB |
| 31 | prime | 31/16, a quarter-tone below the octave | 1145 | F♯4 +45¢ | 0 dB |

Reading the table as a composer:

- **2, 3, 5 spell a G major triad** (G, D, B), in pure just intonation: the fifth 2¢ wide of
  equal temperament, the third 14¢ flat (sweeter).
- **7, 11, 13 leave the tempered world**: a blues-like flat seventh, a quarter-tone tritone and
  a neutral sixth. These are the "strange" notes that give the melody its colour.
- **17, 19, 23, 29, 31** land near chromatic notes (G♯, B♭, C♯, F, F♯), some within a few cents,
  some a quarter-tone away.
- **Powers of 2** (4, 8, 16) are the tonic in higher octaves, **9** is the ninth and **27** the
  Pythagorean sixth: prime powers are, literally, the overtones of their prime.

### 2.3 How the two systems fit

The drone's root E2 and the melody's tonic G2 are **300 cents apart: exactly a minor third**. Put
the melody's G–B–D over the drone's E and you get **E minor 7** (E–G–B–D), the same chord the
first zeros sketch on their own. So the piece hovers between E minor (the drone) and G major (the
plucked primes), the relative-key pair, while the higher primes (7, 11, 13 …) and the inharmonic
drone partials keep both from settling into a common-practice key.

## 3. Intonation as a process: hearing the zeros tune the primes

With few zeros the spikes are broad, and their peaks sit **between** the integers. A peak at
x = 7.39 is not "7": the piece plays it at its exact position, so it comes out as a microtonal
ghost (F♯4 −37¢ instead of 7's F4 −31¢). In the first bar, with a single zero, the peaks fall at:

| peak at x | played as | becomes, once enough zeros are added |
|---|---|---|
| 1.94 | G2 −53¢ | 2 (G2) |
| 3.03 | D3 +20¢ | 3 (D3 +2¢) |
| 4.74 | B♭2 −8¢ | 5 (B2 −14¢) |
| 7.39 | F♯4 −37¢ | 7 (F4 −31¢) |
| 11.53 | C♯4 +33¢ | 11 (C♯4 −49¢) |
| 18.0 | A3 +4¢ | 17 and 19 split apart |
| 28.08 | F4 −26¢ | 29 (F4 +30¢) |

Each time zeros are added, the peaks narrow (their width shrinks roughly like x / N) and slide
onto the integers. Ghosts that sit on no prime fade out; new peaks appear (4, 8, 9 as bells; 17
and 19 separating out of one broad bump). By 34 zeros every note of the bar is a prime or prime
power within a few cents. Movement II is therefore a slow **tuning-in**: a process piece in the
sense of Steve Reich's phase music, where the process is mathematical convergence.

## 4. Rhythm: a sieve on a 30-step grid

The bar sweeps x from 1.5 to 31.5 in 8 seconds, so every whole number has its own moment:
3.75 integers per second, **a 30-step sequencer** (at 3.75 steps/s, about 56 BPM if a step is a
sixteenth). The active steps are the primes and prime powers:

```
step:   2  3  4  5  .  7  8  9  .  11 .  13 .  .  16 17 .  19 .  .  .  23 .  25 .  27 .  29 .  31
        P  P  b  P     P  b  b     P     P        b  P     P           P     b     b     P     P
```

(P = pluck on a prime, b = bell on a prime power)

This is a **sieve rhythm** in Xenakis's sense, and it has the shape of the primes themselves: busy
at the start (2, 3, 4, 5 almost back to back), thinning out further along (the gap from 23 to 29
is six steps), because primes thin out like 1/ln x. Inside each bar, the music decelerates.

Movement III leaves the bar and sweeps x **exponentially** from 31.5 to 260, so each second covers
the same *ratio* of the number line (×1.05 per second) rather than the same distance. Measured
that way, primes get denser further out (about x / ln x of them per unit of ln x), so the notes
speed up: an accelerando built into the number line.

## 5. Dynamics come from arithmetic

The height of a spike, after normalisation, is Λ(n)/ln n: **1 at a prime, 1/2 at a square, 1/3 at
a cube**. That is used directly as the note's loudness:

- primes are played at full level;
- squares (4, 9, 25) at −6 dB;
- cubes (8, 27) at −9.5 dB;
- 16 = 2⁴ at −12 dB (often too quiet to be detected at all: honest, its spike really is the
  smallest).

Prime powers also play on bells mixed 4 dB under the plucks, so relative to a prime they sound at
−10, −13.5 and −16 dB.

So the accent pattern of every bar is the arithmetic of its numbers. One more effect is audible:
with a fixed number of zeros, primes far along the number line are resolved less sharply and come
out softer (about −2.6 dB by x ≈ 220 with 500 zeros), so movement III fades slightly as it runs
out towards the edge of what the zeros can resolve.

## 6. Form

| movement | time | number line | zeros | musical function |
|---|---|---|---|---|
| I. Pole | 0:00–0:16 | 1.2 → 3.2 | 0 → 1 | introduction: drone only; the first zero fades in |
| II. Adding zeros | 0:16–1:52 | the bar 1.5 → 31.5, 12 times | 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 200 | the process: ghosts tune into primes (Fibonacci steps keep each change audible) |
| III. Further out | 1:52–2:36 | 31.5 → 260, exponential | 200 → 500 | development: accelerando, rising register |
| IV. Critical line | 2:36–2:52 | the bar, twice | 500 | climax: the most exact version of the bar |
| V. Reflection | 2:52–3:24 | the bar, 4 times | 34, 8, 2, 1 | coda: zeros are removed and the primes dissolve back into waves |

The arc is **order emerging from noise and returning to it**, framed by the drone. The
"Reflection" title borrows the zeta function's symmetry s ↔ 1 − s as a metaphor for the return.

The alternative versions in `compositions/proposals/` change only these parameters: *Prime Pulse*
uses a 5-second bar (faster, more rhythmic); *Deep Strip* a 12-second bar with the drone an octave
lower and a long reverb; *Critical Strip (revised)* shortens movement II, turns IV into a call (the
bar as breath alone) and response, and runs V backwards so the piece ends on 3 then 2.

## 7. Orchestration and sound design

| voice | instrument | why |
|---|---|---|
| zeros | additive sine drone, one partial per zero, tremolo from cos(γ ln x) | the zeros *are* a spectrum |
| primes | Karplus–Strong plucked string (2.8 s decay, calibrated at every pitch) | the source video compares adding zeros to playing chords on a guitar |
| prime powers | two-operator FM bell an octave up (modulator ratio 1.4, itself inharmonic) | "overtones" of their prime, as the video calls them |
| ghosts | dull, short pluck at −5 dB | wrong notes should sound tentative |
| the sum itself | band-passed noise (250–2500 Hz) shaped by the spike curve | you hear the waveform breathe |
| main term (pole of ζ at s = 1) | low sine, E1 | the smooth part of the formula, with no primes in it |

Mix: drone −13 dB, plucks −5 dB, bells 4 dB under plucks, breath −28 dB, pole −21 dB; a 3.6 s
convolution reverb at 24 % wet; soft saturation and a −1 dBFS peak ceiling.

## 8. The radio edit: *The Sound of the Primes*

The main track takes the same mathematics and plays it with real instruments. Every note still comes from
the explicit formula; what changes is tempo, tuning (equal temperament), arrangement and instruments.
There is no bass line or drum part: nothing is added that the zeros did not produce
(`compositions/commercial/the_sound_of_the_primes.toml`, rendered with `zeta-music produce`).

- **Tempo and metre: 112.5 BPM in 5/4.** One 8-second bar of the number line is exactly three bars of
  5/4, and every whole number lands on an odd sixteenth, so the primes sit on the grid.
- **Tuning: tempered.** The sampled instruments play standard pitches; the exact microtonal tuning lives
  in the original pieces.
- **Instruments:** upright piano (primes), vibraphone (prime powers), a slow synth pad on the first
  zeros' chord, voiced openly (zeros), reverb, delay and bus compression.

| Time | Section | Zeros | What happens |
|---|---|---|---|
| 0:00 | Intro | 0 → 1 | the pad and the first zero |
| 0:16 | Tuning in | 1, 2, 3, 5, 8, 13, 34, 200 | eight bars; wrong notes slide onto the primes |
| 1:20 | Chorus | 500 | everything locks in on the exact primes |
| 1:52 | Further out | 500 | x runs from 31.5 to 130: an accelerando through larger primes |
| 2:16 | Chorus | 500 | back to the bar |
| 2:32 | Outro | 55, 13 | the bar runs backwards while zeros are removed; it ends on 3, then 2 |

Mastered to −14 LUFS for streaming. The score is public and `zeta-music produce … --midi-only` writes
its MIDI; the recording needs the sampled instruments, and the separate instrument stems are not
distributed.

## 9. Using it yourself

**With your own instruments.** Every render writes a MIDI file next to the WAV. Each note carries
its exact microtonal pitch as a pitch bend (range ±2 semitones, set by RPN on every channel) and
gets its own channel while it sounds, so it works with any MPE-capable synth or with multi-timbral
setups. Programs: nylon guitar for primes, tubular bells for prime powers, pizzicato for ghosts.
Time is in seconds (60 BPM, one beat = one second).

**Writing your own score.** A score is a TOML file. Musically, its parameters mean:

| parameter | musical meaning |
|---|---|
| `loop` | bar length (tempo): 8 s gives 3.75 numbers per second |
| `x_start`, `x_end` | which stretch of the number line the bar plays (which primes, which register) |
| `zeros_steps` | how in tune each bar is; the sequence of steps is the shape of the process |
| `sweep = "exp"` | accelerando through the number line instead of a fixed grid |
| `pluck_base_hz` | key of the melody (its harmonic series), e.g. 98 Hz = G |
| `drone_base_hz` | root of the drone (where the first zero sits), e.g. 82.41 Hz = E |
| `drone_gain`, `pluck_gain`, `breath_gain` | per-section orchestration (0 mutes a voice) |
| `[mix]` | balance, reverb, loudness |

Try moving `pluck_base_hz` relative to `drone_base_hz`: a minor third apart (the default) gives
the E minor / G major ambiguity; a unison makes the drone's E the tonic of the primes; a tritone
makes the two systems clash.

**Hearing it interactively.** The web demo (`make web`, then open
`output/web/hear-the-primes.html`) lets you drag the number of zeros and play the bar, with the
individual waves drawn under their sum.

## 10. Glossary

- **Zero (of ζ)** — a complex number ρ = ½ + iγ where the zeta function vanishes. γ is its
  "frequency". The Riemann Hypothesis says the real part is always ½.
- **Explicit formula** — the identity writing the primes as a sum of one wave per zero.
- **Prime power** — p^k (4, 8, 9, 25, 27 …). Their spikes are 1/k as tall as a prime's.
- **Salience** — the normalised spike height used as loudness (1 at primes, 1/k at p^k).
- **Ghost** — a spike that has not yet settled on an integer because too few zeros are used.
- **Just intonation / prime limit** — tuning by whole-number ratios; "7-limit" uses ratios built
  from 2, 3, 5 and 7. Here every prime contributes its own interval.
- **Inharmonic** — a spectrum whose partials are not whole multiples of a fundamental (bells,
  gongs; here, the zeros).
- **Cents** — 1/100 of an equal-tempered semitone; 1200 cents = one octave.
