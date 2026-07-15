from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal

from replaypos.models import Track, TrackPoint

# Fixed tick interval (ms).  On Windows the default clock resolution
# is ~15 ms, so 16 ms gives the best consistent rate.
_TICK_MS = 16


class PlaybackController(QObject):
    """Drives track playback with configurable speed and position signals.

    At each tick (every ``_TICK_MS`` ms) we advance enough points to
    match the requested *data‑time / real‑time* ratio.  This means the
    controller works correctly at any speed, even 120× (≈6 min data per
    3 real seconds).
    """

    position_changed = pyqtSignal(object)  # TrackPoint
    playing_changed = pyqtSignal(bool)
    finished = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._track: Track | None = None
        self._current_index: int = 0
        self._speed: float = 1.0
        self._is_playing: bool = False
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)  # type: ignore[attr-defined]
        self._timer.timeout.connect(self._tick)
        self._avg_step_s: float = 1.0  # cached average step in seconds

    # ── public API ────────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_point(self) -> TrackPoint | None:
        if self._track and 0 <= self._current_index < len(self._track.points):
            return self._track.points[self._current_index]
        return None

    def load_track(self, track: Track) -> None:
        """Load a new track for playback."""
        self._track = track
        self._avg_step_s = _average_step_seconds(track)
        self.stop()

    def play(self) -> None:
        """Start or resume playback."""
        if not self._track or not self._track.points:
            return
        if self._current_index >= len(self._track.points) - 1:
            self._current_index = 0
        self._is_playing = True
        self._timer.start(_TICK_MS)
        self.playing_changed.emit(True)

    def pause(self) -> None:
        """Pause playback (keep position)."""
        self._timer.stop()
        self._is_playing = False
        self.playing_changed.emit(False)

    def stop(self) -> None:
        """Stop playback and reset to the beginning."""
        self._timer.stop()
        self._is_playing = False
        self._current_index = 0
        self.playing_changed.emit(False)
        if self._track and self._track.points:
            self.position_changed.emit(self._track.points[0])

    def set_speed(self, speed: float) -> None:
        """Set playback speed multiplier (no upper limit)."""
        self._speed = max(0.25, speed)
        # No timer restart needed — _tick calculates advance per tick

    def seek_to_index(self, index: int) -> None:
        """Jump to a specific point index."""
        if not self._track or not self._track.points:
            return
        self._current_index = max(0, min(index, len(self._track.points) - 1))
        self.position_changed.emit(self._track.points[self._current_index])

    def seek_to_position(self, fraction: float) -> None:
        """Jump to a fractional position along the track (0.0 – 1.0)."""
        if not self._track or not self._track.points:
            return
        idx = int(fraction * (len(self._track.points) - 1))
        self.seek_to_index(idx)

    # ── internals ─────────────────────────────────────────────────

    def _compute_advance(self) -> int:
        """Return how many points to skip per tick at current speed."""
        tick_sec = _TICK_MS / 1000.0
        # At speed 120 we want to consume 120 data-seconds per real second.
        # Each point represents _avg_step_s data-seconds, so we need
        #   speed * tick_sec / _avg_step_s  points per tick.
        if self._avg_step_s <= 0:
            return 1
        advance = max(1, round(self._speed * tick_sec / self._avg_step_s))
        return advance

    def _tick(self) -> None:
        """Advance one or more points — called by QTimer every ``_TICK_MS``."""
        if not self._track or not self._track.points:
            self.stop()
            return
        n = len(self._track.points)
        if self._current_index >= n - 1:
            self.stop()
            self.finished.emit()
            return

        step = self._compute_advance()
        target = min(n - 1, self._current_index + step)
        self._current_index = target
        self.position_changed.emit(self._track.points[target])


# ── helper ─────────────────────────────────────────────────────────


def _average_step_seconds(track: Track) -> float:
    """Return the mean time between consecutive points (seconds)."""
    if not track or len(track.points) < 2:
        return 1.0
    total = (
        track.points[-1].timestamp - track.points[0].timestamp
    ).total_seconds()
    return total / max(len(track.points) - 1, 1)
