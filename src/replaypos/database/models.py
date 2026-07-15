from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProjectDB(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    metadata_json: Mapped[str | None] = mapped_column(Text)

    tracks: Mapped[list["TrackDB"]] = relationship(
        "TrackDB", back_populates="project", cascade="all, delete-orphan"
    )
    objects: Mapped[list["ProjectObjectDB"]] = relationship(
        "ProjectObjectDB", back_populates="project", cascade="all, delete-orphan"
    )


class TrackDB(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    source_file: Mapped[str | None] = mapped_column(String(512))
    source_format: Mapped[str] = mapped_column(String(32), default="csv")
    point_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    metadata_json: Mapped[str | None] = mapped_column(Text)

    project: Mapped["ProjectDB"] = relationship("ProjectDB", back_populates="tracks")
    points: Mapped[list["TrackPointDB"]] = relationship(
        "TrackPointDB", back_populates="track", cascade="all, delete-orphan"
    )


class TrackPointDB(Base):
    __tablename__ = "track_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[str] = mapped_column(String(36), ForeignKey("tracks.id"), nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    utm_easting: Mapped[float] = mapped_column(Float, nullable=False)
    utm_northing: Mapped[float] = mapped_column(Float, nullable=False)
    utm_zone: Mapped[str] = mapped_column(String(8), nullable=False)
    elevation: Mapped[float | None] = mapped_column(Float)
    sog: Mapped[float | None] = mapped_column(Float)
    cog: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    speed: Mapped[float | None] = mapped_column(Float)
    acceleration: Mapped[float | None] = mapped_column(Float)
    gps_accuracy: Mapped[float | None] = mapped_column(Float)
    gps_satellites: Mapped[int | None] = mapped_column(Integer)
    gps_fix_quality: Mapped[int | None] = mapped_column(Integer)
    gps_hdop: Mapped[float | None] = mapped_column(Float)
    ukc_front: Mapped[float | None] = mapped_column(Float)
    ukc_aft: Mapped[float | None] = mapped_column(Float)
    tide: Mapped[float | None] = mapped_column(Float)
    water_level: Mapped[float | None] = mapped_column(Float)

    track: Mapped["TrackDB"] = relationship("TrackDB", back_populates="points")


class EventDB(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    track_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tracks.id"))
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[str | None] = mapped_column(Text)
    position_easting: Mapped[float | None] = mapped_column(Float)
    position_northing: Mapped[float | None] = mapped_column(Float)
    position_zone: Mapped[str | None] = mapped_column(String(8))


class ChapterDB(Base):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    track_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tracks.id"))
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    chapter_type: Mapped[str] = mapped_column(String(32), default="manual")
    color: Mapped[str] = mapped_column(String(16), default="#4A90D9")
    icon: Mapped[str | None] = mapped_column(String(64))


class ProjectObjectDB(Base):
    __tablename__ = "project_objects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    geometry_json: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(16), default="#4A90D9")
    icon: Mapped[str | None] = mapped_column(String(64))
    warning_distance: Mapped[float | None] = mapped_column(Float)
    alarm_distance: Mapped[float | None] = mapped_column(Float)

    project: Mapped["ProjectDB"] = relationship("ProjectDB", back_populates="objects")


class SettingsDB(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
