# ReplayPos

GIS-based replay, analysis and reporting platform for mobile objects (vessels, vehicles, machinery).

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
uv run pytest

# Run
uv run python -m replaypos
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
