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
