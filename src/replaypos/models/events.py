from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(StrEnum):
    ALARM = "alarm"
    WARNING = "warning"
    NOTE = "note"
    INSPECTION = "inspection"
    GPS_ERROR = "gps_error"
    PROXIMITY_ALERT = "proximity_alert"
    ZONE_ENTERED = "zone_entered"
    ZONE_EXITED = "zone_exited"
    STOP_DETECTED = "stop_detected"
    START_DETECTED = "start_detected"
    SPEED_EXCEEDED = "speed_exceeded"
    COURSE_CHANGE = "course_change"
    MANUAL = "manual"


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Event(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    track_id: UUID | None = None
    event_type: EventType = EventType.MANUAL
    severity: EventSeverity = EventSeverity.INFO
    message: str = ""
    details: str | None = None
    position_utm_easting: float | None = None
    position_utm_northing: float | None = None
    position_utm_zone: str | None = None
    metadata: dict = Field(default_factory=dict)
