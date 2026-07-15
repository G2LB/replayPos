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

## 2026-07-15 — Pydantic data models

Implemented all core Pydantic v2 models:
- `Position` — UTM-based with `pyproj` WGS84 conversion via `@cached_property`
- `Navigation` — SOG, COG, Heading, Speed with validation
- `GPS` — Accuracy, satellites, FixQuality enum
- `Survey` — UKC front/aft, Tide, Water Level, Depth
- `TrackPoint` — Composiet model met position + navigation + gps + survey
- `Track` — Container met binary search `get_point_at()`, duration/timing properties
- `Event` — EventType/EventSeverity enums, position + metadata
- `Chapter` — ChapterType enum, duration formatting, kleur/icoon
- `ProjectObject` — ObjectGeometry (point/line/polygon/circle) met Shapely
- `SafetyZone` — Configurable warning/alarm zones per object
- `Project` — Full project container met tracks, objects, events, chapters
- 23 unit tests — all passing
- Ruff lint — all checks passed
