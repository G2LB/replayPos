from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChapterType(StrEnum):
    STOP = "stop"
    TRANSIT = "transit"
    MANEUVERING = "maneuvering"
    STATIONARY = "stationary"
    WORKING = "working"
    SURVEY = "survey"
    COURSE_CHANGE = "course_change"
    PROXIMITY = "proximity"
    ZONE = "zone"
    MANUAL = "manual"
    TIDE_CHANGE = "tide_change"
    UKC_ALERT = "ukc_alert"


class Chapter(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID | None = None
    name: str = ""
    description: str | None = None
    start_time: datetime
    end_time: datetime
    chapter_type: ChapterType = ChapterType.MANUAL
    color: str = "#4A90D9"
    icon: str | None = None
    metadata: dict = Field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()

    @property
    def duration_formatted(self) -> str:
        total = int(self.duration_seconds)
        h, remainder = divmod(total, 3600)
        m, s = divmod(remainder, 60)
        if h > 0:
            return f"{h}h {m:02d}m {s:02d}s"
        if m > 0:
            return f"{m}m {s:02d}s"
        return f"{s}s"
