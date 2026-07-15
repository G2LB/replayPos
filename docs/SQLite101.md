# ReplayPos SQLite Guide

## Database location

```
~/.replaypos/replaypos.db
```

## Open the database

```bash
sqlite3 ~/.replaypos/replaypos.db
```

## Useful SQLite commands

```sql
-- List all tables
.tables

-- Show schema of a table
.schema track_points

-- Pretty output
.headers on
.mode column

-- Show indexes
SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'track_points';
```

## Schema overview

```
projects         1──N  tracks          1──N  track_points
projects         1──N  project_objects
tracks           1──N  events
tracks           1──N  chapters
projects         1──N  events
projects         1──N  chapters
```

## Example queries

### Projects

```sql
-- All projects
SELECT id, name, client, created_at FROM projects ORDER BY updated_at DESC;

-- Project count
SELECT COUNT(*) FROM projects;

-- Find by name
SELECT * FROM projects WHERE name LIKE '%Dredge%';
```

### Tracks

```sql
-- Tracks for a project
SELECT id, name, point_count, source_file, created_at
FROM tracks
WHERE project_id = 'your-project-uuid'
ORDER BY created_at;

-- Track statistics
SELECT
    COUNT(*) AS total_points,
    MIN(timestamp) AS start_time,
    MAX(timestamp) AS end_time,
    ROUND(AVG(sog), 2) AS avg_sog,
    MAX(sog) AS max_sog
FROM track_points
WHERE track_id = 'your-track-uuid';
```

### Track points (performance)

```sql
-- Count points per track
SELECT track_id, COUNT(*) AS cnt
FROM track_points
GROUP BY track_id
ORDER BY cnt DESC;

-- Points in time range
SELECT COUNT(*) FROM track_points
WHERE track_id = 'uuid'
  AND timestamp BETWEEN '2026-07-01 00:00:00' AND '2026-07-01 01:00:00';

-- Last N points (for QC check)
SELECT timestamp, utm_easting, utm_northing, sog, cog
FROM track_points
WHERE track_id = 'uuid'
ORDER BY timestamp DESC
LIMIT 5;
```

### Events

```sql
-- All events for a project
SELECT timestamp, event_type, severity, message
FROM events
WHERE project_id = 'uuid'
ORDER BY timestamp;

-- Filter by type and severity
SELECT timestamp, message
FROM events
WHERE project_id = 'uuid'
  AND event_type IN ('alarm', 'warning')
  AND severity = 'critical'
ORDER BY timestamp;

-- Event count by type
SELECT event_type, COUNT(*) AS cnt
FROM events
WHERE project_id = 'uuid'
GROUP BY event_type
ORDER BY cnt DESC;
```

### Chapters

```sql
-- Chapters with duration
SELECT
    name,
    chapter_type,
    start_time,
    end_time,
    ROUND((julianday(end_time) - julianday(start_time)) * 86400, 0) AS duration_seconds,
    color
FROM chapters
WHERE track_id = 'uuid'
ORDER BY start_time;

-- Chapter types distribution
SELECT chapter_type, COUNT(*) AS cnt
FROM chapters
GROUP BY chapter_type
ORDER BY cnt DESC;
```

### Settings

```sql
-- All settings
SELECT * FROM settings;

-- Get specific setting
SELECT value FROM settings WHERE key = 'theme';
```

## Python examples (REPL)

```python
from replaypos.database.database import DatabaseService
from replaypos.database.repository import ProjectRepository, TrackRepository
from replaypos.models import Project, Track, TrackPoint, Position

# Open database
db = DatabaseService()
db.init_db()
session = db.create_session()

# --- Create project ---
repo = ProjectRepository(session)
project = Project(name="Dredge Job 2026", client="ACME")
repo.create(project)
print(f"Created project: {project.id}")

# --- List projects ---
for p in repo.list_all():
    print(f"  {p.name} ({p.client})")

# --- Load track points in batches ---
track_repo = TrackRepository(session)
points = track_repo.load_points(track_id)

# Process in chunks (1000 per page)
for i in range(0, len(points), 1000):
    batch = points[i:i+1000]
    sog_values = [p.navigation.sog for p in batch if p.navigation]
    print(f"Batch {i//1000}: avg SOG = {sum(sog_values)/len(sog_values):.1f}")

session.close()

# --- Settings ---
db.set_setting("theme", "dark")
db.set_setting("recent_projects", ["uuid1", "uuid2"])
print(db.get_setting("theme"))  # "dark"

db.close()
```

## Performance tips

- `track_points` table has an index on `(track_id, timestamp)` for fast range queries
- Bulk inserts use `INSERT` with batches of 1000 rows (`executemany`)
- Reading large tracks uses `yield_per(1000)` to stream results (not load all into memory)
- WAL mode enabled for concurrent reads during writes
- The Dorsch sample has ~46K points, Gator has ~68K points — both insert in <1 second

```sql
-- Check query performance
EXPLAIN QUERY PLAN
SELECT * FROM track_points
WHERE track_id = 'uuid'
  AND timestamp BETWEEN '2026-07-01' AND '2026-07-02';
-- Look for "SEARCH" (uses index) vs "SCAN" (full table scan)

-- Database size
PRAGMA page_count;
PRAGMA page_size;
SELECT (SELECT page_count FROM pragma_page_count) *
       (SELECT page_size FROM pragma_page_size) / 1024 / 1024 AS size_mb;

-- Optimize
PRAGMA optimize;
VACUUM;
```
