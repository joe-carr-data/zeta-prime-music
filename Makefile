# Every deliverable builds from a clean clone: `make all` (needs ffmpeg for video/clips).
.PHONY: install test lint render proposals literal explain video clips video-j web hero site produce all

OUT := output
PROP := $(OUT)/proposals

install:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

$(OUT)/critical_strip.wav: compositions/critical_strip.toml
	uv run zeta-music -v render compositions/critical_strip.toml -o $(OUT)

render: $(OUT)/critical_strip.wav

$(PROP)/B_prime_pulse.wav: compositions/proposals/prime_pulse.toml
	uv run zeta-music render compositions/proposals/prime_pulse.toml -o $(PROP) --name B_prime_pulse --no-plot

$(PROP)/F_critical_strip_revised.wav: compositions/proposals/critical_strip_revised.toml
	uv run zeta-music render compositions/proposals/critical_strip_revised.toml -o $(PROP) --name F_critical_strip_revised --no-plot

$(PROP)/C_deep_strip.wav: compositions/proposals/deep_strip.toml
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
	uv run zeta-music video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav --aspect 9:16 --start 16 --end 64 --caption "One zero, one wave: the notes are out of tune" --end-card -o $(OUT)/clips/1_first_zeros.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav --aspect 9:16 --start 64 --end 112 --caption "Add more zeros and the primes lock into tune" --end-card -o $(OUT)/clips/2_primes_lock_in.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav --aspect 9:16 --start 112 --end 156 --caption "Hundreds of zeros: twin primes 101 and 103 ring apart" --end-card -o $(OUT)/clips/3_further_out.mp4
	uv run zeta-music video compositions/critical_strip.toml --audio $(OUT)/critical_strip.wav --aspect 9:16 --start 172 --end 208 --caption "Take the zeros away and the primes dissolve" --end-card -o $(OUT)/clips/4_reflection.mp4
	uv run zeta-music video compositions/proposals/prime_pulse.toml --audio $(PROP)/B_prime_pulse.wav --aspect 9:16 --start 10 --end 70 --caption "Add the zeros of ζ one by one and hear the primes come into tune" --end-card -o $(OUT)/clips/5_prime_pulse_full_arc.mp4

# Proposal J (produced radio edit): full video + five vertical clips synced to the produced master.
# Produce it first (needs the Kontakt states, see the score), or point J_WAV at an existing master.
J_SCORE := compositions/commercial/critical_strip_radio_kontakt.toml
J_WAV ?= $(OUT)/commercial_j/critical_strip_radio_kontakt.wav
J_DIR := $(PROP)/J_video
J_VIDEO := uv run zeta-music video $(J_SCORE) --audio $(J_WAV) --title "The Sound of the Primes" --end-card
J_CLIP := $(J_VIDEO) --aspect 9:16

$(J_DIR)/J_full.mp4: $(J_SCORE) $(J_WAV)
	@mkdir -p $(J_DIR)
	$(J_VIDEO) -o $@
$(J_DIR)/J_1_tuning_in.mp4: $(J_SCORE) $(J_WAV)
	@mkdir -p $(J_DIR)
	$(J_CLIP) --start 16 --end 64 --caption "Add the zeros of ζ one by one and hear the primes come into tune" -o $@
$(J_DIR)/J_2_chorus.mp4: $(J_SCORE) $(J_WAV)
	@mkdir -p $(J_DIR)
	$(J_CLIP) --start 72 --end 112 --caption "500 zeros: the sound of the primes" -o $@
$(J_DIR)/J_3_further_out.mp4: $(J_SCORE) $(J_WAV)
	@mkdir -p $(J_DIR)
	$(J_CLIP) --start 112 --end 152 --caption "Further out, the primes thin — and speed up" -o $@
$(J_DIR)/J_4_outro.mp4: $(J_SCORE) $(J_WAV)
	@mkdir -p $(J_DIR)
	$(J_CLIP) --start 136 --end 176 --caption "Take the zeros away and the primes dissolve into 3 … 2" -o $@
$(J_DIR)/J_5_best_of.mp4: $(J_SCORE) $(J_WAV)
	@mkdir -p $(J_DIR)
	$(J_CLIP) --start 56 --end 112 --caption "13 zeros, then 34, 200, 500: the primes lock into tune" -o $@

video-j: $(addprefix $(J_DIR)/,J_full.mp4 J_1_tuning_in.mp4 J_2_chorus.mp4 J_3_further_out.mp4 J_4_outro.mp4 J_5_best_of.mp4)

web:
	uv run python scripts/build_web.py

site: web
	uv run python scripts/build_web.py docs/demo.html --standalone

produce:
	uv run --extra produce zeta-music -v produce compositions/commercial/critical_strip_radio.toml -o $(OUT)/commercial

hero:
	uv run zeta-music animate -o docs/media/hero.gif --mp4 $(OUT)/hero.mp4

all: lint test proposals explain video clips web
