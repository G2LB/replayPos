from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from replaypos.models import Track, TrackPoint


class PlaybackController(QObject):
    """Drives track playback with configurable speed and position signals."""

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
        self._timer.timeout.connect(self._tick)

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
        self.stop()

    def play(self) -> None:
        """Start or resume playback."""
        if not self._track or not self._track.points:
            return
        if self._current_index >= len(self._track.points) - 1:
            self._current_index = 0
        self._is_playing = True
        self._timer.start(self._compute_interval())
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
        """Set playback speed multiplier (0.25 – 16)."""
        self._speed = max(0.25, min(speed, 16.0))
        if self._is_playing:
            self._timer.setInterval(self._compute_interval())

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

    def _compute_interval(self) -> int:
        """Calculate timer interval (ms) based on time delta to next point."""
        if not self._track or len(self._track.points) < 2:
            return 100
        n = len(self._track.points)
        # Use average step duration for smoother playback
        total_secs = (
            self._track.points[-1].timestamp - self._track.points[0].timestamp
        ).total_seconds()
        avg_step_ms = (total_secs / max(n - 1, 1)) * 1000
        adjusted = avg_step_ms / self._speed
        return max(16, int(adjusted))

    def _tick(self) -> None:
        """Advance one step — called by QTimer."""
        if not self._track or not self._track.points:
            self.stop()
            return
        n = len(self._track.points)
        # Advance to the next point that is strictly ahead in time
        if self._current_index < n - 1:
            self._current_index += 1
            self.position_changed.emit(self._track.points[self._current_index])
            # Recalculate interval for the next step (variable-rate data)
            self._timer.setInterval(self._compute_interval())
        else:
            self.stop()
            self.finished.emit()
