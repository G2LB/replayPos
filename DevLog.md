# ReplayPos – DevLog

## 2026-07-15 — Project initialization

- Initialized project with `uv init`, Python 3.13.13
- Set up modular directory structure (22 Python packages)
- Created `pyproject.toml` with all dependencies
- Added `.gitignore`, `README.md`, `DevLog.md`
- Set up GitHub Actions CI workflow (Ruff + PyTest)
- Sample data (Dorsch + Gator CSV) placed in `tests/fixtures/`
- Git initialized with `main` + `develop` branches
- `uv run ruff check src/` — all checks passed
- All 30 core dependencies installed (PyQt6, SQLAlchemy, pyproj, etc.)
