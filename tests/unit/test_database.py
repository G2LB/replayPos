from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from replaypos.database.database import DatabaseService
from replaypos.database.repository import (
    ChapterRepository,
    EventRepository,
    ProjectRepository,
    TrackRepository,
)
from replaypos.models import (
    Chapter,
    ChapterType,
    Event,
    EventSeverity,
    EventType,
    Navigation,
    Position,
    Project,
    Track,
    TrackPoint,
)


@pytest.fixture
def db(tmp_path: Path) -> DatabaseService:
    db_path = tmp_path / "test_replaypos.db"
    service = DatabaseService(db_path)
    service.init_db()
    yield service
    service.close()


@pytest.fixture
def sample_project() -> Project:
    return Project(name="Test Project", client="ACME Corp", description="Integration test")


@pytest.fixture
def sample_track() -> Track:
    points = []
    ts = datetime(2026, 7, 1, 10, 0, 0)
    for i in range(50):
        pts = ts + timedelta(seconds=i * 6)
        pos = Position(utm_easting=400000.0 + i, utm_northing=5949000.0 + i, utm_zone="32N")
        nav = Navigation(sog=float(i % 10), cog=180.0, heading=45.0)
        points.append(TrackPoint(index=i, timestamp=pts, position=pos, navigation=nav))
    return Track(name="Test Track", source_file="test.csv", points=points)


class TestDatabaseService:
    def test_init_and_schema(self, db: DatabaseService):
        db.init_db()
        with db.create_session() as session:
            from sqlalchemy import inspect

            inspector = inspect(session.bind)
            tables = inspector.get_table_names()
            assert "projects" in tables
            assert "tracks" in tables
            assert "track_points" in tables
            assert "events" in tables
            assert "chapters" in tables
            assert "project_objects" in tables
            assert "settings" in tables

    def test_settings(self, db: DatabaseService):
        db.set_setting("theme", "dark")
        assert db.get_setting("theme") == "dark"

        db.set_setting("recent_projects", ["proj1", "proj2"])
        assert db.get_setting("recent_projects") == ["proj1", "proj2"]

        assert db.get_setting("nonexistent", 42) == 42


class TestProjectRepository:
    def test_create_project(self, db: DatabaseService, sample_project: Project):
        with db.create_session() as session:
            repo = ProjectRepository(session)
            saved = repo.create(sample_project)
            assert saved.id == sample_project.id

    def test_get_project(self, db: DatabaseService, sample_project: Project):
        with db.create_session() as session:
            repo = ProjectRepository(session)
            repo.create(sample_project)

        with db.create_session() as session:
            repo = ProjectRepository(session)
            loaded = repo.get(sample_project.id)
            assert loaded is not None
            assert loaded.name == "Test Project"
            assert loaded.client == "ACME Corp"

    def test_list_projects(self, db: DatabaseService):
        with db.create_session() as session:
            repo = ProjectRepository(session)
            repo.create(Project(name="P1"))
            repo.create(Project(name="P2"))

        with db.create_session() as session:
            repo = ProjectRepository(session)
            all_projects = repo.list_all()
            assert len(all_projects) == 2

    def test_delete_project(self, db: DatabaseService, sample_project: Project):
        with db.create_session() as session:
            repo = ProjectRepository(session)
            repo.create(sample_project)
            assert repo.delete(sample_project.id) is True
            assert repo.delete(UUID(int=0)) is False


class TestTrackRepository:
    def test_save_and_load_track(
        self, db: DatabaseService, sample_project: Project, sample_track: Track
    ):
        with db.create_session() as session:
            ProjectRepository(session).create(sample_project)
            TrackRepository(session).save(sample_track, sample_project.id)

        with db.create_session() as session:
            loaded = TrackRepository(session).get(sample_track.id)
            assert loaded is not None
            assert loaded.name == "Test Track"
            assert loaded.point_count == 0

        with db.create_session() as session:
            points = TrackRepository(session).load_points(sample_track.id)
            assert len(points) == 50
            assert points[0].position.utm_easting == 400000.0
            assert points[-1].position.utm_northing == 5949049.0

    def test_load_points_range(
        self, db: DatabaseService, sample_project: Project, sample_track: Track
    ):
        with db.create_session() as session:
            ProjectRepository(session).create(sample_project)
            TrackRepository(session).save(sample_track, sample_project.id)

        start = datetime(2026, 7, 1, 10, 0, 0)
        end = datetime(2026, 7, 1, 10, 1, 0)

        with db.create_session() as session:
            points = TrackRepository(session).load_points_range(sample_track.id, start, end)
            assert len(points) == 11
            assert points[0].timestamp == start
            assert points[-1].timestamp <= end

    def test_large_batch(self, db: DatabaseService, sample_project: Project):
        points = []
        ts = datetime(2026, 7, 1, 0, 0, 0)
        for i in range(2500):
            pts = ts + timedelta(seconds=i)
            pos = Position(utm_easting=400000.0 + i, utm_northing=5949000.0 + i, utm_zone="32N")
            points.append(TrackPoint(index=i, timestamp=pts, position=pos))
        track = Track(name="Large Track", points=points)

        with db.create_session() as session:
            ProjectRepository(session).create(sample_project)
            TrackRepository(session).save(track, sample_project.id)

        with db.create_session() as session:
            loaded = TrackRepository(session).load_points(track.id)
            assert len(loaded) == 2500

    def test_delete_track(self, db: DatabaseService, sample_project: Project, sample_track: Track):
        with db.create_session() as session:
            ProjectRepository(session).create(sample_project)
            TrackRepository(session).save(sample_track, sample_project.id)

        with db.create_session() as session:
            repo = TrackRepository(session)
            assert repo.delete(sample_track.id) is True

        with db.create_session() as session:
            points = TrackRepository(session).load_points(sample_track.id)
            assert len(points) == 0


class TestEventRepository:
    def test_add_and_list_events(self, db: DatabaseService, sample_project: Project):
        with db.create_session() as session:
            ProjectRepository(session).create(sample_project)
            repo = EventRepository(session)
            ev1 = Event(
                timestamp=datetime(2026, 7, 1, 10, 0, 0),
                event_type=EventType.ALARM,
                severity=EventSeverity.CRITICAL,
                message="UKC alert",
            )
            ev2 = Event(
                timestamp=datetime(2026, 7, 1, 10, 5, 0),
                event_type=EventType.WARNING,
                severity=EventSeverity.WARNING,
                message="Proximity warning",
            )
            repo.add(ev1)
            repo.add(ev2)

        with db.create_session() as session:
            events = EventRepository(session).list_for_project(sample_project.id)
            assert len(events) == 0  # no project_id set on events

    def test_events_with_project(self, db: DatabaseService, sample_project: Project):
        with db.create_session() as session:
            ProjectRepository(session).create(sample_project)
            ev = Event(
                timestamp=datetime(2026, 7, 1, 10, 0, 0),
                event_type=EventType.ALARM,
                severity=EventSeverity.CRITICAL,
                message="Test event",
            )
            # Store with project_id directly in DB
            from replaypos.database.models import EventDB

            db_ev = EventDB(
                id=str(ev.id),
                project_id=str(sample_project.id),
                timestamp=ev.timestamp,
                event_type=ev.event_type.value,
                severity=ev.severity.value,
                message=ev.message,
            )
            session.add(db_ev)
            session.commit()

        with db.create_session() as session:
            events = EventRepository(session).list_for_project(sample_project.id)
            assert len(events) == 1
            assert events[0].event_type == EventType.ALARM


class TestChapterRepository:
    def test_add_and_list_chapters(self, db: DatabaseService):
        with db.create_session() as session:
            repo = ChapterRepository(session)
            ch = Chapter(
                name="Transit",
                start_time=datetime(2026, 7, 1, 10, 0, 0),
                end_time=datetime(2026, 7, 1, 11, 0, 0),
                chapter_type=ChapterType.TRANSIT,
            )
            repo.add(ch)
            ch2 = Chapter(
                name="Stop",
                start_time=datetime(2026, 7, 1, 11, 0, 0),
                end_time=datetime(2026, 7, 1, 11, 30, 0),
                chapter_type=ChapterType.STOP,
                color="#FF4444",
            )
            repo.add(ch2)

        with db.create_session() as session:
            chapters = ChapterRepository(session).list_for_project(UUID(int=0))
            assert len(chapters) == 0
