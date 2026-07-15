from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from shapely.geometry import LineString, Point, Polygon

from replaypos.models.chapters import Chapter
from replaypos.models.events import Event
from replaypos.models.track import Track


class ProjectObjectType(StrEnum):
    BRIDGE = "bridge"
    JETTY = "jetty"
    BUOY = "buoy"
    PIPELINE = "pipeline"
    CABLE = "cable"
    WINDMILL = "windmill"
    WORK_AREA = "work_area"
    ANCHORAGE = "anchorage"
    CRANE = "crane"
    PONTOON = "pontoon"
    EQUIPMENT = "equipment"
    FREE_MARKER = "free_marker"
    POLYGON = "polygon"
    LINE = "line"
    CIRCLE = "circle"


class ObjectGeometry(BaseModel):
    type: str  # "point", "linestring", "polygon", "circle"
    utm_zone: str = "32N"
    point: tuple[float, float] | None = None  # easting, northing
    line: list[tuple[float, float]] | None = None
    polygon: list[tuple[float, float]] | None = None
    circle_center: tuple[float, float] | None = None
    circle_radius: float | None = None

    @property
    def shapely(self):
        if self.type == "point" and self.point:
            return Point(self.point[0], self.point[1])
        if self.type == "linestring" and self.line:
            return LineString(self.line)
        if self.type == "polygon" and self.polygon:
            return Polygon(self.polygon)
        if self.type == "circle" and self.circle_center:
            from shapely.geometry import Point as ShapelyPoint
            cx, cy = self.circle_center
            return ShapelyPoint(cx, cy).buffer(self.circle_radius or 0)
        return None


class SafetyZone(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = ""
    geometry: ObjectGeometry
    warning_distance: float = 250.0
    alarm_distance: float = 100.0
    color: str = "#FF4444"
    enabled: bool = True


class ProjectObject(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID | None = None
    name: str = ""
    object_type: ProjectObjectType = ProjectObjectType.FREE_MARKER
    geometry: ObjectGeometry
    safety_zones: list[SafetyZone] = Field(default_factory=list)
    color: str = "#4A90D9"
    icon: str | None = None
    metadata: dict = Field(default_factory=dict)


class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = ""
    client: str | None = None
    description: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tracks: list[Track] = Field(default_factory=list)
    objects: list[ProjectObject] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
