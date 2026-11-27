.PHONY: install test lint render literal explain all
install:
	uv sync
test:
	uv run pytest -q
lint:
	uv run ruff check . && uv run ruff format --check .
render:
	uv run zeta-music -v render compositions/critical_strip.toml -o output
literal:
	uv run zeta-music literal log -o output/zeros_chord.wav -d 12
	uv run zeta-music literal linear -o output/prime_clicks.wav -d 12
explain:
	uv run zeta-music explain -o output/explainer.png
all: lint test render literal explain

video:
	uv run zeta-music -v video compositions/critical_strip.toml --audio output/critical_strip.wav -o output/critical_strip.mp4

clips:
	mkdir -p output/clips
	uv run zeta-music video compositions/critical_strip.toml --audio output/critical_strip.wav --aspect 9:16 --start 16 --end 64 -o output/clips/1_first_zeros.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio output/critical_strip.wav --aspect 9:16 --start 64 --end 112 -o output/clips/2_primes_lock_in.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio output/critical_strip.wav --aspect 9:16 --start 112 --end 156 -o output/clips/3_further_out.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio output/critical_strip.wav --aspect 9:16 --start 172 --end 208 -o output/clips/4_reflection.mp4
	uv run zeta-music video compositions/proposals/prime_pulse.toml --audio output/proposals/B_prime_pulse.wav --aspect 9:16 --start 10 --end 70 -o output/clips/5_prime_pulse_full_arc.mp4
