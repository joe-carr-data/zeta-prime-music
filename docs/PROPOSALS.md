# How the proposals are made

All proposals use the same engine and the same mathematics. Only the score parameters differ.

| | Score / command | Bar (loop) | Drone (γ₁ →) | Plucks (harmonics of) | Mix & room | Length |
|---|---|---|---|---|---|---|
| A Critical Strip | `compositions/critical_strip.toml` | 8 s × 12 | E2 82.41 Hz, −13 dB, tremolo 0.35 | G2 98 Hz | reverb 3.6 s, 24 % wet | 3:28 |
| B Prime Pulse | `compositions/proposals/prime_pulse.toml` | 5 s × 12 | E2, −18 dB, tremolo 0.6 | C3 130.81 Hz | reverb 3.6 s, 14 % wet | 2:24 |
| C Deep Strip | `compositions/proposals/deep_strip.toml` | 12 s × 12 | E1 41.2 Hz, −9 dB | C2 65.41 Hz | reverb 6 s, 38 % wet | 4:44 |
| D Zeros' chord | `zeta-music literal log -d 12` | — | 200 zeros as sines, γ₁ → 110 Hz, weight 1/\|ρ\| | — | none | 0:12 |
| E Prime clicks | `zeta-music literal linear -d 12` | — | ψ'₂₀₀(x) − 1 played as a waveform, x: 1.5 → 400 | — | none | 0:12 |

A–C share the five-movement form (Pole → Adding zeros 1,2,3,5…200 → Further out to x=260 with
500 zeros → Critical line → Reflection), so they have identical note *events* (181 primes,
46 prime powers, 29 ghosts) at different tempi, registers and timbres.

Make a new proposal: copy a TOML, change `loop` (and the section `duration` = loop × bars),
`drone_base_hz`, `pluck_base_hz`, `[mix]`; then `uv run zeta-music render <file> -o output/proposals`.
