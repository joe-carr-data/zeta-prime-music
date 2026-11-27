# Every deliverable builds from a clean clone: `make all` (needs ffmpeg for video/clips).
.PHONY: install test lint render proposals literal explain video clips web all

OUT := output
PROP := $(OUT)/proposals

install:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

$(OUT)/critical_strip.wav:
	uv run zeta-music -v render compositions/critical_strip.toml -o $(OUT)

render: $(OUT)/critical_strip.wav

$(PROP)/B_prime_pulse.wav:
	uv run zeta-music render compositions/proposals/prime_pulse.toml -o $(PROP) --name B_prime_pulse --no-plot

$(PROP)/F_critical_strip_revised.wav:
	uv run zeta-music render compositions/proposals/critical_strip_revised.toml -o $(PROP) --name F_critical_strip_revised --no-plot

$(PROP)/C_deep_strip.wav:
	uv run zeta-music render compositions/proposals/deep_strip.toml -o $(PROP) --name C_deep_strip --no-plot

proposals: render $(PROP)/B_prime_pulse.wav $(PROP)/C_deep_strip.wav $(PROP)/F_critical_strip_revised.wav
	cp $(OUT)/critical_strip.wav $(PROP)/A_critical_strip.wav
	uv run zeta-music literal log -o $(PROP)/D_literal_zeros_chord.wav -d 12
	uv run zeta-music literal linear -o $(PROP)/E_literal_prime_clicks.wav -d 12
	uv run python scripts/encode_m4a.py $(PROP)

literal:
	uv run zeta-music literal log -o $(OUT)/zeros_chord.wav -d 12
	uv run zeta-music literal linear -o $(OUT)/prime_clicks.wav -d 12

explain:
	uv run zeta-music explain -o $(OUT)/explainer.png

video: render
	uv run zeta-music -v video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav -o $(OUT)/critical_strip.mp4

clips: render $(PROP)/B_prime_pulse.wav
	mkdir -p $(OUT)/clips
	uv run zeta-music video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav --aspect 9:16 --start 16 --end 64 -o $(OUT)/clips/1_first_zeros.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav --aspect 9:16 --start 64 --end 112 -o $(OUT)/clips/2_primes_lock_in.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav --aspect 9:16 --start 112 --end 156 -o $(OUT)/clips/3_further_out.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav --aspect 9:16 --start 172 --end 208 -o $(OUT)/clips/4_reflection.mp4
	uv run zeta-music video compositions/proposals/prime_pulse.toml --audio $(PROP)/B_prime_pulse.wav --aspect 9:16 --start 10 --end 70 -o $(OUT)/clips/5_prime_pulse_full_arc.mp4

web:
	uv run python scripts/build_web.py

all: lint test proposals explain video clips web
