from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from replaypos.models.chapters import Chapter
from replaypos.models.events import Event
from replaypos.models.gps import GPS
from replaypos.models.navigation import Navigation
from replaypos.models.position import Position
from replaypos.models.survey import Survey


class TrackPoint(BaseModel):
    index: int
    timestamp: datetime
    position: Position
    navigation: Navigation | None = None
    gps: GPS | None = None
    survey: Survey | None = None
    elevation: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Track(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str | None = None
    source_file: str | None = None
    source_format: str = "csv"
    points: list[TrackPoint] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def point_count(self) -> int:
        return len(self.points)

    @property
    def duration_seconds(self) -> float:
        if len(self.points) < 2:
            return 0.0
        return (self.points[-1].timestamp - self.points[0].timestamp).total_seconds()

    @property
    def start_time(self) -> datetime | None:
        return self.points[0].timestamp if self.points else None

    @property
    def end_time(self) -> datetime | None:
        return self.points[-1].timestamp if self.points else None

    @property
    def unique_dates(self) -> list[date]:
        """Sorted list of unique dates covered by this track's points."""
        seen: set[date] = {p.timestamp.date() for p in self.points}
        return sorted(seen)

    @staticmethod
    def _is_stationary(pt: TrackPoint) -> bool:
        nav = pt.navigation
        if nav is None:
            return True
        sog_zero = nav.sog is None or nav.sog == 0.0
        speed_zero = nav.speed is None or nav.speed == 0.0
        return sog_zero and speed_zero

    @property
    def stationary_dates(self) -> set[date]:
        """Dates where every point has SOG/speed == 0 (or both absent)."""
        by_date: dict[date, list[TrackPoint]] = defaultdict(list)
        for p in self.points:
            by_date[p.timestamp.date()].append(p)
        return {d for d, pts in by_date.items() if all(self._is_stationary(p) for p in pts)}

    def filter_by_dates(self, targets: set[date]) -> Track:
        """Return a new Track with only points whose date is in *targets*."""
        filtered = [p for p in self.points if p.timestamp.date() in targets]
        reindexed = [p.model_copy(update={"index": i}) for i, p in enumerate(filtered)]
        return self.model_copy(update={"points": reindexed, "chapters": [], "events": []})

    def filter_by_date(self, target: date | str) -> Track:
        """Return a new Track with only points whose timestamp matches *target*.

        Parameters
        ----------
        target : date or str
            A ``datetime.date`` or a ``'YYYY-MM-DD'`` string.

        Returns
        -------
        Track
            A copy with filtered (re-indexed) points and empty chapters/events.
        """
        if isinstance(target, str):
            target = date.fromisoformat(target)
        filtered = [p for p in self.points if p.timestamp.date() == target]
        reindexed = [p.model_copy(update={"index": i}) for i, p in enumerate(filtered)]
        return self.model_copy(update={"points": reindexed, "chapters": [], "events": []})

    def get_point_at(self, timestamp: datetime) -> TrackPoint | None:
        lo, hi = 0, len(self.points) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.points[mid].timestamp < timestamp:
                lo = mid + 1
            elif self.points[mid].timestamp > timestamp:
                hi = mid - 1
            else:
                return self.points[mid]
        if hi < 0:
            return self.points[0]
        if lo >= len(self.points):
            return self.points[-1]
        diff_lo = abs((self.points[lo].timestamp - timestamp).total_seconds())
        diff_hi = abs((self.points[hi].timestamp - timestamp).total_seconds())
        return self.points[lo] if diff_lo < diff_hi else self.points[hi]
