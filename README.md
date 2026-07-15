# ReplayPos

GIS-based replay, analysis and reporting platform for mobile objects (vessels, vehicles, machinery).

[![CI](https://github.com/anomalyco/replaypos/actions/workflows/ci.yml/badge.svg)](https://github.com/anomalyco/replaypos/actions/workflows/ci.yml)

> 📖 [Development Log](DevLog.md) · [SQLite Schema & Patterns](docs/SQLite101.md)

## Features

- **CSV Import** — Universal CSV Import Wizard with column mapping and reusable templates
- **Playback** — YouTube-like timeline with speed control (0.25× – 16×)
- **Map** — Interactive MapLibre GL map with track overlay, north arrow, and scale bar
- **Analysis** — Distance, SOG, COG, Heading, acceleration, stop detection, GPS quality
- **Chapters & Events** — Automatic chapter generation and event detection
- **Project Objects** — Bridges, buoys, pipelines, cables, windmills, work areas, and more
- **Proximity Detection** — Configurable warning and alarm zones per object
- **Export** — MP4 video with chapters, PDF reports
- **Plugins** — Extensible plugin system (AIS, GPX, NMEA, AI)

## Quick Start

```bash
# Install uv (if not installed)
# Windows: irm https://astral.sh/uv/install.ps1 | iex

# Run
uv run replaypos
```

## Development

```bash
# Setup
uv sync --dev

# Lint
uv run ruff check src/

# Test
uv run pytest   # → testresults_all.md (auto)

# Update per-step test reports
uv run python scripts/update_test_reports.py   # → testresults_stap{2,3,4}.md

# Run
uv run python -m replaypos
```

## Test Results

### pytest results

| Stap | Module | Tests | ✅ Passed | ❌ Failed |
|------|--------|-------|-----------|-----------|
| 2 | [Pydantic Models](testresults_stap2_models.md) | 23 | 23 | 0 |
| 3 | [SQLite Database](testresults_stap3_database.md) | 13 | 13 | 0 |
| 4 | [CSV Import](testresults_stap4_import.md) | 38 | 38 | 0 |
| **Total** | | **74** | **74** | **0** |

**Failed tests:** ✅ None — all 74 passed

📊 [testresults_all.md](testresults_all.md)
```

## Architecture

```
src/replaypos/
├── analysis/      — Track analysis algorithms
├── chapters/      — Chapter engine
├── database/      — SQLite persistence
├── detection/     — Proximity detection
├── events/        — Event engine
├── exporters/     — MP4/PDF export
├── importers/     — CSV import wizard
├── mapping/       — Map widget (MapLibre GL)
├── models/        — Pydantic data models
├── playback/      — Playback controller
├── plugins/       — Plugin system
├── project/       — Project management
├── reports/       — PDF report generation
├── services/      — Application services
├── settings/      — Configuration
├── timeline/      — Timeline widget
├── ui/            — Main window and widgets
├── utils/         — Utilities
└── video/         — Video import
```

## License

Proprietary — All rights reserved.
