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

## 2026-07-15 — Database layer (SQLite + SQLAlchemy)

- `database/models.py` — 7 ORM tabellen (projects, tracks, track_points, events, chapters, project_objects, settings)
- `database/database.py` — DatabaseService met WAL mode, PRAGMA optimalisaties, settings get/set
- `database/repository.py` — Repository pattern: ProjectRepository, TrackRepository (bulk INSERT 1000/batch), EventRepository, ChapterRepository
- `settings/settings_manager.py` — SettingsManager via database
- `docs/SQLite101.md` — Referentie gids met SQL + Python voorbeelden
- 13 database tests — all passing
- Performance: 2500 punten bulk insert <1s, yield_per voor streaming

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

## 2026-07-15 — MCP setup, CSV import wizard, CI & GitHub push

- **MCP Server Setup** — Configured `opencode.jsonc` with two MCP servers:
  - `filesystem` — local `@modelcontextprotocol/server-filesystem` for project file access
  - `github` — local `@modelcontextprotocol/server-github` authenticated via `GITHUB_TOKEN`
- **Project agent rules** (`AGENTS.md`) — Python 3.13, uv, Pydantic v2, SQLAlchemy 2.0, UTM-first policy
- **CSV Import** (Stap 4) — Full import pipeline:
  - `csv_importer.py` — Core parsing: `parse_float`, `parse_int`, `parse_zone`, delimiter detection, timestamp parsing
  - `csv_wizard.py` — `CsvColumnMapper` (column-to-field mapping), `TrackPointBuilder` (raw row → `TrackPoint`), `CsvReader` (preview + full read)
  - `csv_filter.py` — `FilterEngine` for stop detection (speed-based segmentation), chapter generation, data reduction estimation
  - Templates: `dorsch_survey.json` + `gator_logger.json` reusable column mapping templates with `TemplateManager` (list/load/save/delete)
- **Nerd Font icons** — `mapping/assets/icons.py` with `NerdIcon` enum (110+ icons), `ICON_MAP`, `get_icon()`, `get_marker_html()`, NERD_FONTS_CSS
- **Navigation model fix** — COG/Heading validation changed from `lt=360.0` to `le=360.0` (inclusive upper bound)
- **Test infrastructure** — Added `pytest-md` + `pytest-emoji` for Markdown test reports; auto-generates `testresults_all.md`
- **CI/CD** — GitHub Actions workflow (`.github/workflows/ci.yml`) with Ruff lint + PyTest on push/PR
- **38 CSV import tests** — all passing (74 total, all green)
- **GitHub repo created** — `https://github.com/G2LB/replayPos` (public), `develop` branch pushed

## 2026-07-15 — Main window & Map widget (Stap 5, steps 1+2)

- **`ui/main_window.py`** — `MainWindow(QMainWindow)` with:
  - File menu: Import CSV (launches `CsvImportWizard`), Exit
  - View menu: toggle Map/Timeline docks
  - Toolbar: Play/Pause/Stop buttons + Speed combo (disabled until track loaded)
  - Dock areas: Map (right), Timeline (bottom, placeholder)
  - Status bar with track info
  - `main()` entry point — creates `QApplication`, shows window, runs event loop
- **`mapping/map_widget.py`** — `MapWidget` embedding MapLibre GL via `QWebEngineView`:
  - MapLibre GL JS v4 from CDN (no bundling)
  - `QWebChannel` for Python ↔ JavaScript bidirectional communication
  - Dark matter basemap (CartoDB), navigation controls, scale bar, north arrow
  - `load_track()` — converts `Track` → GeoJSON FeatureCollection (LineString + start/end markers)
  - `fit_bounds()`, `highlight_point()`, `clear()` methods
  - SVG marker images for start (green triangle) and end (red square)
- App now starts: `uv run python -m replaypos` shows main window with map
- All 74 existing tests still pass; ruff lint clean
