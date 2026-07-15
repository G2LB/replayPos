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

## 2026-07-15 — Day filter + per-day map layers + track colors (Stap 5.3)

- **Per-day track colors** — GeoJSON `stroke` property per day alternates `#3b82f6` / `#93c5fd`, JS data-driven `line-color: ['get', 'stroke']`
- **`DayFilterWidget`** (`ui/day_filter.py`) — QToolButton + QMenu with checkable QActions per date, "All dates" master toggle, "Hide stationary days" toggle, italic for stationary days, `selection_changed` signal
- **`Track.stationary_dates`** — property that finds dates where all points have SOG/speed == 0
- **`Track.filter_by_dates(targets)`** — cheap O(n) filter (no per-point `model_copy`)
- **Per-day JS layers** — `_track_to_geojson_by_day()` creates one source+layer per day; `loadTrack` instantiates them all; `toggleDay(dateStr, visible)` sets layer visibility instantly (no GeoJSON re-upload)
- **`MapWidget.set_day_visible()`** — Python bridge for `toggleDay()`

## 2026-07-15 — Cumulative progress trail + 6-minute interval markers

- **JS progress trail** — `progressCoords` array, `appendProgressPoint()`, `resetProgress()` — amber line (`#fbbf24`) grows one coord per playback tick
- **JS interval markers** — `loadIntervals()` drops yellow dot markers every 6 minutes on the map; `highlightInterval()` pulses the current interval
- **Python `MapWidget`** — `load_intervals()`, `append_progress_point()`, `highlight_interval()`, `reset_progress()` bridge methods
- **`MainWindow._compute_intervals()`** — walks filtered track points, emits `{coords, time, point_idx}` at every 6-minute clock boundary
- **`_on_position_changed`** — appends progress point each tick + advances interval highlight when `point_idx` is crossed
- **Time-of-replay overlay** on map — `nf-md-timer_marker` Nerd Font icon + ISO datetime in bottom-left overlay; `updateTimeDisplay()` JS + `MapWidget.set_time_display()` Python
- **`clearMap()`** now cleans up all progress/interval layers

## 2026-07-15 — Nerd Font icons in PyQt UI

- **`src/replaypos/ui/nerd_font.py`** — new module:
  - `init_nerd_fonts()` — checks system, local cache, then downloads NerdFontsSymbolsOnly.zip from GitHub releases v3.3.0, extracts TTF, and loads via `QFontDatabase.addApplicationFont()`
  - `nerd_icon(css_class, size, color) → QIcon` — renders glyph on transparent pixmap
  - `nerd_font(size) → QFont` — for direct widget use
  - Multi-strategy fallback: system → cached TTF → direct CDN TTF → zip download
  - Font validation with magic-byte check (`\x00\x01\x00\x00`, `OTTO`, `true`, `ttcf`)
  - Logging at every step; graceful fallback to empty icons if font unavailable
- **MainWindow** — menu/toolbar icons: File→Import CSV (`nf-fae-file_import`), Export to DB (`nf-md-database_export`), Play/Pause (`nf-md-play`/`nf-md-pause`), Stop (`nf-md-stop`), Fit (`nf-md-map_marker`)
- **`_on_export_db`** — placeholder method for future database export

## 2026-07-15 — 120× playback speed + timeline interval markers

- **PlaybackController rewritten** — fixed 16ms `PreciseTimer` tick; `_compute_advance()` calculates multi-point skip per tick (`round(speed × tick_sec / avg_step_seconds)`). No upper speed limit; at 120×: ~6 min data per 3 real seconds
- **`_average_step_seconds()`** — caches mean inter-point delta for accurate advance calculation
- **Speed combo** — added 60× and 120× options
- **TimelineWidget** — `load_intervals()`, `set_current_interval()`, `clear()` manage `_intervals` list; `paintEvent` draws gray tick marks above the track bar at each 6-minute boundary, active interval in amber `#fbbf24`
- **MainWindow._apply_filtered_track** — passes `_interval_list` to timeline
- **MainWindow._on_position_changed** — calls `timeline.set_current_interval()` in sync with map `highlight_interval()`
- All 74 tests passing; ruff lint + format clean
