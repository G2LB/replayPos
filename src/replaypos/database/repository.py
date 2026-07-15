from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from replaypos.database.models import (
    ChapterDB,
    EventDB,
    ProjectDB,
    TrackDB,
    TrackPointDB,
)
from replaypos.models import (
    Chapter,
    Event,
    Position,
    Project,
    Track,
    TrackPoint,
)


def _project_to_db(project: Project) -> ProjectDB:
    return ProjectDB(
        id=str(project.id),
        name=project.name,
        client=project.client,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        metadata_json=json.dumps(project.metadata) if project.metadata else None,
    )


def _project_from_db(row: ProjectDB) -> Project:
    return Project(
        id=UUID(row.id),
        name=row.name,
        client=row.client,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=json.loads(row.metadata_json) if row.metadata_json else {},
    )


def _track_to_db(track: Track, project_id: UUID) -> TrackDB:
    return TrackDB(
        id=str(track.id),
        project_id=str(project_id),
        name=track.name,
        source_file=track.source_file,
        source_format=track.source_format,
        point_count=track.point_count,
        created_at=track.created_at,
        metadata_json=json.dumps(track.metadata) if track.metadata else None,
    )


def _track_from_db(row: TrackDB) -> Track:
    return Track(
        id=UUID(row.id),
        name=row.name,
        source_file=row.source_file,
        source_format=row.source_format,
        created_at=row.created_at,
        metadata=json.loads(row.metadata_json) if row.metadata_json else {},
    )


def _trackpoint_to_dict(tp: TrackPoint, track_id: UUID) -> dict:
    return {
        "track_id": str(track_id),
        "index": tp.index,
        "timestamp": tp.timestamp,
        "utm_easting": tp.position.utm_easting,
        "utm_northing": tp.position.utm_northing,
        "utm_zone": tp.position.utm_zone,
        "elevation": tp.elevation,
        "sog": tp.navigation.sog if tp.navigation else None,
        "cog": tp.navigation.cog if tp.navigation else None,
        "heading": tp.navigation.heading if tp.navigation else None,
        "speed": tp.navigation.speed if tp.navigation else None,
        "acceleration": tp.navigation.acceleration if tp.navigation else None,
        "gps_accuracy": tp.gps.accuracy if tp.gps else None,
        "gps_satellites": tp.gps.satellites if tp.gps else None,
        "gps_fix_quality": (
            int(tp.gps.fix_quality) if tp.gps and tp.gps.fix_quality is not None else None
        ),
        "gps_hdop": tp.gps.hdop if tp.gps else None,
        "ukc_front": tp.survey.ukc_front if tp.survey else None,
        "ukc_aft": tp.survey.ukc_aft if tp.survey else None,
        "tide": tp.survey.tide if tp.survey else None,
        "water_level": tp.survey.water_level if tp.survey else None,
    }


def _trackpoint_from_row(row: TrackPointDB) -> TrackPoint:
    return TrackPoint(
        index=row.index,
        timestamp=row.timestamp,
        position=Position(
            utm_easting=row.utm_easting,
            utm_northing=row.utm_northing,
            utm_zone=row.utm_zone,
            elevation=row.elevation,
        ),
    )


BATCH_SIZE = 1000


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, project: Project) -> Project:
        db = _project_to_db(project)
        self.session.add(db)
        self.session.commit()
        return project

    def get(self, project_id: UUID) -> Project | None:
        row = self.session.query(ProjectDB).filter(ProjectDB.id == str(project_id)).first()
        return _project_from_db(row) if row else None

    def list_all(self) -> list[Project]:
        rows = self.session.query(ProjectDB).order_by(ProjectDB.updated_at.desc()).all()
        return [_project_from_db(r) for r in rows]

    def update(self, project: Project) -> Project:
        row = self.session.query(ProjectDB).filter(ProjectDB.id == str(project.id)).first()
        if not row:
            raise KeyError(f"Project {project.id} not found")
        row.name = project.name
        row.client = project.client
        row.description = project.description
        row.updated_at = datetime.now()
        row.metadata_json = json.dumps(project.metadata) if project.metadata else None
        self.session.commit()
        return project

    def delete(self, project_id: UUID) -> bool:
        row = self.session.query(ProjectDB).filter(ProjectDB.id == str(project_id)).first()
        if not row:
            return False
        self.session.delete(row)
        self.session.commit()
        return True


class TrackRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, track: Track, project_id: UUID) -> Track:
        db_track = _track_to_db(track, project_id)
        self.session.add(db_track)
        self.session.flush()

        points_data = [_trackpoint_to_dict(tp, track.id) for tp in track.points]
        for i in range(0, len(points_data), BATCH_SIZE):
            batch = points_data[i : i + BATCH_SIZE]
            self.session.execute(TrackPointDB.__table__.insert(), batch)

        self.session.commit()
        logger.info("Saved track '{}' with {} points", track.name, track.point_count)
        return track

    def get(self, track_id: UUID) -> Track | None:
        row = self.session.query(TrackDB).filter(TrackDB.id == str(track_id)).first()
        return _track_from_db(row) if row else None

    def get_tracks_for_project(self, project_id: UUID) -> list[Track]:
        rows = (
            self.session.query(TrackDB)
            .filter(TrackDB.project_id == str(project_id))
            .order_by(TrackDB.created_at)
            .all()
        )
        return [_track_from_db(r) for r in rows]

    def load_points(self, track_id: UUID) -> list[TrackPoint]:
        rows = (
            self.session.query(TrackPointDB)
            .filter(TrackPointDB.track_id == str(track_id))
            .order_by(TrackPointDB.index)
            .yield_per(BATCH_SIZE)
        )
        return [_trackpoint_from_row(r) for r in rows]

    def load_points_range(self, track_id: UUID, start: datetime, end: datetime) -> list[TrackPoint]:
        rows = (
            self.session.query(TrackPointDB)
            .filter(
                TrackPointDB.track_id == str(track_id),
                TrackPointDB.timestamp >= start,
                TrackPointDB.timestamp <= end,
            )
            .order_by(TrackPointDB.index)
            .yield_per(BATCH_SIZE)
        )
        return [_trackpoint_from_row(r) for r in rows]

    def delete(self, track_id: UUID) -> bool:
        row = self.session.query(TrackDB).filter(TrackDB.id == str(track_id)).first()
        if not row:
            return False
        self.session.delete(row)
        self.session.commit()
        return True


class EventRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, event: Event) -> Event:
        db = EventDB(
            id=str(event.id),
            track_id=str(event.track_id) if event.track_id else None,
            timestamp=event.timestamp,
            event_type=event.event_type.value,
            severity=event.severity.value,
            message=event.message,
            details=event.details,
            position_easting=event.position_utm_easting,
            position_northing=event.position_utm_northing,
            position_zone=event.position_utm_zone,
        )
        self.session.add(db)
        self.session.commit()
        return event

    def list_for_track(self, track_id: UUID) -> list[Event]:
        rows = (
            self.session.query(EventDB)
            .filter(EventDB.track_id == str(track_id))
            .order_by(EventDB.timestamp)
            .all()
        )
        return [_event_from_db(r) for r in rows]

    def list_for_project(self, project_id: UUID) -> list[Event]:
        rows = (
            self.session.query(EventDB)
            .filter(EventDB.project_id == str(project_id))
            .order_by(EventDB.timestamp)
            .all()
        )
        return [_event_from_db(r) for r in rows]

    def list_filtered(
        self, project_id: UUID, event_types: list[str] | None = None, severity: str | None = None
    ):
        query = self.session.query(EventDB).filter(EventDB.project_id == str(project_id))
        if event_types:
            query = query.filter(EventDB.event_type.in_(event_types))
        if severity:
            query = query.filter(EventDB.severity == severity)
        rows = query.order_by(EventDB.timestamp).all()
        return [_event_from_db(r) for r in rows]


class ChapterRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, chapter: Chapter) -> Chapter:
        db = ChapterDB(
            id=str(chapter.id),
            track_id=str(chapter.track_id) if chapter.track_id else None,
            name=chapter.name,
            description=chapter.description,
            start_time=chapter.start_time,
            end_time=chapter.end_time,
            chapter_type=chapter.chapter_type.value,
            color=chapter.color,
            icon=chapter.icon,
        )
        self.session.add(db)
        self.session.commit()
        return chapter

    def list_for_track(self, track_id: UUID) -> list[Chapter]:
        rows = (
            self.session.query(ChapterDB)
            .filter(ChapterDB.track_id == str(track_id))
            .order_by(ChapterDB.start_time)
            .all()
        )
        return [_chapter_from_db(r) for r in rows]

    def list_for_project(self, project_id: UUID) -> list[Chapter]:
        rows = (
            self.session.query(ChapterDB)
            .filter(ChapterDB.project_id == str(project_id))
            .order_by(ChapterDB.start_time)
            .all()
        )
        return [_chapter_from_db(r) for r in rows]


def _event_from_db(row: EventDB) -> Event:
    from replaypos.models.events import EventSeverity, EventType

    return Event(
        id=UUID(row.id),
        track_id=UUID(row.track_id) if row.track_id else None,
        timestamp=row.timestamp,
        event_type=EventType(row.event_type),
        severity=EventSeverity(row.severity),
        message=row.message,
        details=row.details,
        position_utm_easting=row.position_easting,
        position_utm_northing=row.position_northing,
        position_utm_zone=row.position_zone,
    )


def _chapter_from_db(row: ChapterDB) -> Chapter:
    from replaypos.models.chapters import ChapterType

    return Chapter(
        id=UUID(row.id),
        track_id=UUID(row.track_id) if row.track_id else None,
        name=row.name,
        description=row.description,
        start_time=row.start_time,
        end_time=row.end_time,
        chapter_type=ChapterType(row.chapter_type),
        color=row.color,
        icon=row.icon,
    )
