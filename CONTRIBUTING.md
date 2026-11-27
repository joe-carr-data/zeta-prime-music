# Contributing to Zeta Prime Music

Thanks for your interest. Contributions of code, scores and musical ideas are all welcome.

## Set up

```bash
uv sync --extra plot     # Python ≥ 3.12; ffmpeg is needed for video, Node for the web parity tests
make test lint
```

## Ways to contribute

- **A new score.** Copy a file from `compositions/`, change the bar length, key, zero counts or
  sections, and render it with `uv run zeta-music render <score.toml> -o output`. Scores that
  show a new musical idea are welcome as pull requests in `compositions/proposals/`. The
  [guide for musicians](docs/FOR_MUSICIANS.md) explains what every parameter means musically.
- **The engine.** Bug fixes, new voices or mappings, performance. Keep the mathematics honest:
  every note should be traceable to the explicit formula, and documented in
  `docs/COMPOSITION.md`.
- **The site and demo.** Pages live in `docs/`; the instrument's source is
  `web/hear-the-primes.src.html` (build with `make site`).

## Guidelines

- Add or update tests for every change (`tests/`); regression tests should state the bug they
  guard against in their docstring.
- Run `make test lint` before opening a pull request; CI runs the same checks on Python 3.12 and
  3.13.
- Keep commit messages short and descriptive (`fix: …`, `feat: …`, `docs: …`).
- Rendered media is not committed except the web-sized files used by the site in `docs/media/`.

## Licence

By contributing you agree that code contributions are licensed under MIT (`LICENSE`) and media
contributions under CC BY 4.0 (`LICENSE-MEDIA.md`).
