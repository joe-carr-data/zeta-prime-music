# Prompt for a literature survey

Copy everything in the block below.

```
I'm building an algorithmic music composition based on the Riemann zeta function, specifically the
"music of the primes" idea: the von Mangoldt explicit formula
  ψ'(x) = 1 − 2x^{−1/2} Σ_γ cos(γ ln x) − 1/(x(x²−1)),
where each nontrivial zero ρ = ½ + iγ contributes one oscillation and summing ~200 zeros produces
spikes at the primes and smaller spikes at prime powers. My current piece maps each zero to a
drone partial (f ∝ γ), detects peaks of the truncated sum as the number line x is swept, and plays
them as plucked notes whose pitch is the octave-folded harmonic x/2^⌊log₂x⌋ (so 3 → fifth,
5 → major third, 7 → harmonic seventh).

Please research and write a structured report (with citations) covering:

1. PRIOR ART — existing sonifications/compositions of the zeta zeros or primes: e.g. Marcus du
   Sautoy "The Music of the Primes", Matthew Watkins' zeta-zero sonifications and the "Zeta
   Zeros" track, Mazur & Stein "Prime Numbers and the Riemann Hypothesis" (the "sound" chapter),
   3Blue1Brown, Numberphile, Odlyzko's data, any academic papers on sonifying ζ, prime
   rhythms (e.g. Tom Johnson, Iannis Xenakis sieves), and the From First Principles podcast
   ep. 69. What mappings did they use (zero→pitch, prime→rhythm, log-time)? What worked
   perceptually?

2. MATHEMATICS that could give richer musical structure, with exact formulas:
   - Weil explicit formula / Guinand–Weil with smooth test functions (best windows to trade
     spike sharpness vs ringing).
   - Pair correlation of zeros (Montgomery–Dyson, GUE statistics) — how to make it audible
     (level repulsion as "consonance"?).
   - Dirichlet L-functions and primes in arithmetic progressions (Chebyshev's bias) as separate
     "voices"/instruments; zeros of L(s,χ) mod 3, mod 4.
   - Riemann's R(x) and the Gram points / Riemann–Siegel Z(t) as a waveform (Z(t) is real —
     can it be played directly?).
   - Prime gaps, twin primes and the Hardy–Littlewood constants as rhythmic material.

3. PSYCHOACOUSTICS & COMPOSITION: tuning choices for inharmonic spectra (Sethares'
   "Tuning, Timbre, Spectrum, Scale" — dissonance curves for the zeta-zero spectrum), just
   intonation and the prime limit (Partch, Tenney harmonic distance), how to make a 200-partial
   inharmonic drone sound musical rather than metallic, and how to pace "order emerging from
   noise" over 3–5 minutes.

4. Concrete, implementable recommendations (numbered, ranked by musical impact), each with the
   formula or algorithm needed, for a Python/numpy synthesis engine.

Be rigorous: separate verified mathematical facts from aesthetic opinion, and give sources.
```

Drop the resulting report into `docs/research/` and the autonomous loop will pick up
recommendations from it.
