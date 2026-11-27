# Critical Strip — composition notes

A ~3½-minute piece generated entirely from the explicit formula. Nothing is hand-placed: every
note is a peak of the truncated sum ψ'_N(x), and every drone partial is a zero.

## Mappings (and why they are honest)

| Mathematical object | Sound | Rationale |
|---|---|---|
| Zero ρ_k = ½ + iγ_k | sine partial at `82.41 Hz · γ_k/γ₁` (γ₁ → E2) | Imag. part = frequency (video, 1:05). Inharmonic: the zeros are *not* a harmonic series. |
| weight 1/\|ρ_k\| | partial amplitude | literal coefficient of x^ρ/ρ in ψ(x) |
| cos(γ_k ln x) at the current x | tremolo of partial k | the zero's actual oscillation along the number line |
| peak of the salience curve (normalised oscillatory part of ψ'_N) at x* | plucked string (Karplus–Strong) | the "guitar" of the video |
| peak position x*, nearest integer n | pitch = G2 · (n/2^⌊log₂n⌋) · 2^octave(n) · (x*/n) — folded harmonic of n, detuned by x*/n | primes become just-intonation intervals: 3 → fifth, 5 → major third, 7 → harmonic 7th, 11 → 11th harmonic… Off-integer peaks are *microtonal* — out of tune until enough zeros are present |
| peak height (normalised) → salience ≈ Λ(n)/log n | velocity | primes = 1, p² = ½, p³ = ⅓ — prime powers are literally quieter |
| prime power p^k (k ≥ 2) | FM bell an octave up | the video's "overtone at 4, 8, 16, 9" |
| peak not at a prime power | "ghost" (dull short pluck) | artefact of truncation; disappears as N grows |
| salience curve (clipped to 0–1.5, squared) | breath (band-passed noise) | the sum, heard |
| pole at s = 1 (main term x of ψ(x), i.e. the "1" in ψ'(x)) | low sine, E1 | the smooth part with no primes in it |

## How accurate is "salience"?

Salience is normalised so that, for a fixed n and enough zeros, S(n) → Λ(n)/log n (1 at primes,
½ at squares). With a fixed number of zeros N (largest ordinate T), the error grows with n
(Gonek's uniform Landau formula, error ~ n·log(nT)/T). Measured with 500 zeros (T ≈ 811):

| x range | median S at primes | squares |
|---|---|---|
| 2–30 | 0.99 (0.96–1.01) | 0.46–0.49 |
| 30–100 | 0.92 (0.87–0.96) | 0.43 |
| 100–180 | 0.81 (0.77–0.87) | 0.27–0.34 |
| 180–260 | 0.74 (0.68–0.77) | — |

So in movement III the primes soften as the sweep runs out towards x = 260, the edge of what
500 zeros can resolve. This is kept deliberately as part of the music.

## Form

| # | Movement | x | zeros N | idea |
|---|---|---|---|---|
| I | Pole | 1.2 → 3.2 | 0 → 1 | silence of the integers; the first zero fades in |
| II | Adding zeros | bar 1.5 → 31.5, ×12 (8 s each) | 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 200 | the same bar replayed; ghost notes fade, primes come into tune (the video's "add the first 200") |
| III | Further out | 31.5 → 260 (exponential) | 200 → 500 | accelerando because primes thin only like 1/ln x; register rises |
| IV | Critical line | bar ×2 | 500 | full chord, maximal clarity |
| V | Reflection | bar ×4 | 34, 8, 2, 1 | s ↦ 1 − s: zeros are removed, the primes dissolve back into waves |

## Rendering

`make render` → `output/critical_strip.{wav,mid,events.json,score.png}`. 24-bit/44.1 kHz WAV;
the MIDI file carries per-note pitch bend (±2 semitones, channel rotation) so the microtonal
ghosts survive into a DAW.
