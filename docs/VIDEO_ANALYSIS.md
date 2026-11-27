# Source video analysis

**Source:** screen recording (3 min, 2026-11-27) of an Instagram reel from the *From First
Principles* podcast (ffpod), Episode 69 — "Riemann and the Music of the Primes". Caption:
*"Add the first 200 Riemann zeta zeros…"*. Transcribed automatically, frames sampled
every 3 s.

## What the video argues, step by step

| t (s) | On screen | Claim |
|---|---|---|
| 0–6 | Riemann portrait over a spike plot labelled 2 3 5 7 11 | "It's literally the music of the primes." |
| 6–18 | Diagram of the critical strip: trivial zeros at −2, −4, −6; pole at s = 1; non-trivial zeros on Re(s)=½ | The *non-trivial* zeros (not the trivial ones) locate the primes. |
| 18–30 | π(x) = li(x) − Σ_ρ li(x^ρ) (− log 2 + ∫…), the sum circled | Focus on the *correction term*: a sum over non-trivial zeros ρ. |
| 30–42 | Zeros plotted at ½ + 14.13i, 21.02i, 25.01i, 30.42i | ρ = ½ + iγ; the Riemann Hypothesis = every real part is ½. |
| 42–57 | Graphs of x², x³; then x^ρ = x^{σ+iγ} | What does a complex power mean? |
| 57–75 | x^{σ+iγ} = x^σ e^{iγ ln x} = x^σ (cos(γ ln x) + i sin(γ ln x)) | Euler: an oscillation. **Real part → amplitude, imaginary part → frequency.** |
| 75–96 | Plot of cos(γ₁ ln x), γ₁ = 14.1347251417 | Wavelength grows because of ln x ("if it were just x it'd be a nice cosine"). |
| 96–105 | cos(γ₁ ln x) and cos(γ₂ ln x), γ₂ = 21.0220396388 | Higher γ → higher intrinsic frequency, still stretched. |
| 105–155 | Sum of the first 200 zeros: sharp spikes at 2, 3, 5, 7, 11, 13, 17, 19, 23 | "Like in guitars, when you add notes and you get nice chords … the music of the primes." Density ~ 1/ln x. |
| 155–175 | Same plot, smaller spikes highlighted | Smaller spikes at **prime powers** 4, 8, 16, 9 — "like an overtone", "a beat". |

## Mathematical reconstruction

The plot is the (formal) derivative of von Mangoldt's explicit formula

    ψ(x) = x − Σ_ρ x^ρ/ρ − log 2π − ½ log(1 − x⁻²)
    ψ'(x) = Σ_{p^k} log p · δ(x − p^k) = 1 − 2 x^{−1/2} Σ_{γ>0} cos(γ ln x) − 1/(x(x²−1))

* spike heights ∝ log p — hence the prime powers p^k carry the *same* weight log p as p, but the
  truncated sum smears them over a width ∝ x, so they look smaller (and the video's "overtone"
  intuition: p^k is the k-th "harmonic" of p in log-space, since ln p^k = k ln p).
* The video's li(x^ρ) form (Riemann's π(x)) and the ψ form (von Mangoldt) carry the same
  oscillations x^{ρ}; the ψ form is what produces clean spikes.
* The video's statement "real part = amplitude" ⇒ x^{1/2}: the RH says every zero has the
  *same* amplitude growth, i.e. the "instruments" are all equally loud — the most "balanced"
  orchestra possible (cf. Mazur & Stein's treatment).

## Reproduction in this repo

`zeta-music explain` regenerates the video's panels (single-zero waves, 200-zero sum with spikes
and prime-power "overtones", ψ(x) recovered). Unit tests assert that 200 zeros put the peaks of
ψ'_N on exactly the 16 prime powers ≤ 30.
