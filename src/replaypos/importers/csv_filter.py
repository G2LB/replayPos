from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from replaypos.models import Chapter, ChapterType, TrackPoint


@dataclass
class FilterConfig:
    sog_threshold: float = 0.5
    min_stop_seconds: int = 60
    trim_leading: bool = True
    trim_trailing: bool = True
    create_stop_chapters: bool = True
    use_cog_detection: bool = True
    cog_stddev_threshold: float = 30.0
    cog_window: int = 5


@dataclass
class FilterResult:
    filtered_points: list[TrackPoint] = field(default_factory=list)
    removed_count: int = 0
    kept_count: int = 0
    stop_chapters: list[Chapter] = field(default_factory=list)
    stop_segments: list[tuple[int, int]] = field(default_factory=list)


class FilterEngine:
    def __init__(self, config: FilterConfig | None = None):
        self.config = config or FilterConfig()

    def detect_stops(self, points: list[TrackPoint]) -> FilterResult:
        result = FilterResult()
        n = len(points)
        if n == 0:
            return result

        is_stopped = np.zeros(n, dtype=bool)

        sog_values = np.array([
            p.navigation.sog if p.navigation and p.navigation.sog is not None else np.nan
            for p in points
        ])

        cog_values = np.array([
            p.navigation.cog if p.navigation and p.navigation.cog is not None else np.nan
            for p in points
        ])

        sog_stopped = np.where(
            (sog_values < self.config.sog_threshold) & (~np.isnan(sog_values)),
            True,
            False,
        )

        if self.config.use_cog_detection:
            cog_stddev = self._rolling_std(cog_values, self.config.cog_window)
            cog_stopped = np.where(
                (cog_stddev > self.config.cog_stddev_threshold) & (~np.isnan(cog_stddev)),
                True,
                False,
            )
            is_stopped = sog_stopped | cog_stopped
        else:
            is_stopped = sog_stopped

        stop_segments = self._find_segments(is_stopped)
        result.stop_segments = [
            (s, e) for s, e in stop_segments
            if self._segment_duration(points, s, e) >= self.config.min_stop_seconds
        ]

        keep_mask = np.ones(n, dtype=bool)
        if self.config.trim_leading and result.stop_segments:
            first_stop_end = result.stop_segments[0][1]
            if first_stop_end < n * 0.1:
                keep_mask[:first_stop_end + 1] = False

        if self.config.trim_trailing and result.stop_segments:
            last_stop_start = result.stop_segments[-1][0]
            if last_stop_start > n * 0.9:
                keep_mask[last_stop_start:] = False

        for s, e in result.stop_segments:
            trimmed = False
            if self.config.trim_leading and s < n * 0.1:
                trimmed = True
            if self.config.trim_trailing and e > n * 0.9:
                trimmed = True
            if not trimmed:
                keep_mask[s:e + 1] = False

        result.filtered_points = [p for i, p in enumerate(points) if keep_mask[i]]
        result.kept_count = len(result.filtered_points)
        result.removed_count = n - result.kept_count

        if self.config.create_stop_chapters:
            result.stop_chapters = self._make_chapters(points, result.stop_segments)

        return result

    def estimate_reduction(
        self, points: list[TrackPoint], config: FilterConfig | None = None
    ) -> dict:
        if config:
            old = self.config
            self.config = config
            result = self.detect_stops(points)
            self.config = old
        else:
            result = self.detect_stops(points)

        total = len(points)
        kept = result.kept_count
        return {
            "total": total,
            "kept": kept,
            "removed": total - kept,
            "reduction_pct": round((total - kept) / total * 100, 1) if total > 0 else 0,
            "stops_found": len(result.stop_segments),
            "stop_chapters": len(result.stop_chapters),
        }

    def _rolling_std(self, values: np.ndarray, window: int) -> np.ndarray:
        if window < 2:
            return np.zeros_like(values)
        valid = ~np.isnan(values)
        if not valid.any():
            return np.full_like(values, np.nan)
        wrapped = np.where(np.isnan(values), np.nanmean(values), values)
        result = np.full_like(values, np.nan)
        for i in range(len(values)):
            start = max(0, i - window // 2)
            end = min(len(values), i + window // 2 + 1)
            segment = wrapped[start:end]
            if valid[start:end].sum() >= 2:
                result[i] = np.nanstd(segment)
        return result

    def _find_segments(self, arr: np.ndarray) -> list[tuple[int, int]]:
        segments = []
        i = 0
        n = len(arr)
        while i < n:
            if arr[i]:
                start = i
                while i < n and arr[i]:
                    i += 1
                segments.append((start, i - 1))
            else:
                i += 1
        return segments

    def _segment_duration(self, points: list[TrackPoint], start: int, end: int) -> float:
        if start >= len(points) or end >= len(points):
            return 0.0
        return (points[end].timestamp - points[start].timestamp).total_seconds()

    def _make_chapters(
        self, points: list[TrackPoint], segments: list[tuple[int, int]]
    ) -> list[Chapter]:
        chapters = []
        for i, (s, e) in enumerate(segments):
            ch = Chapter(
                name=f"Stop {i + 1}",
                description=f"Stationary period ({points[e].timestamp - points[s].timestamp})",
                start_time=points[s].timestamp,
                end_time=points[e].timestamp,
                chapter_type=ChapterType.STOP,
                color="#FF4444",
            )
            chapters.append(ch)
        return chapters
