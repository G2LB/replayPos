from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from replaypos.models import Track

# ── colours ──────────────────────────────────────────────────────

_BG_COLOR = QColor("#1e1e2e")
_TRACK_COLOR = QColor("#3b82f6")
_PLAYHEAD_COLOR = QColor("#ef4444")
_CHAPTER_COLORS = [
    QColor("#22c55e"),
    QColor("#f59e0b"),
    QColor("#8b5cf6"),
    QColor("#06b6d4"),
    QColor("#ec4899"),
    QColor("#14b8a6"),
]

# ── helpers ──────────────────────────────────────────────────────

_DUR_FMT = "%H:%M:%S"


def _format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TimelineWidget(QWidget):
    """Horizontal timeline strip with chapters and a draggable playhead."""

    seek_requested = pyqtSignal(float)  # fractional position 0.0 – 1.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setMouseTracking(True)

        self._track: Track | None = None
        self._fraction: float = 0.0  # 0.0 – 1.0
        self._hover_frac: float | None = None
        self._dragging: bool = False

    # ── public API ────────────────────────────────────────────────

    def load_track(self, track: Track) -> None:
        """Set the track to display."""
        self._track = track
        self._fraction = 0.0
        self.update()

    def set_position(self, fraction: float) -> None:
        """Move the playhead to a fractional position."""
        self._fraction = max(0.0, min(fraction, 1.0))
        self.update()

    def clear(self) -> None:
        """Remove track data."""
        self._track = None
        self._fraction = 0.0
        self.update()

    # ── mouse handling ────────────────────────────────────────────

    def _frac_from_pos(self, x: int) -> float:
        w = max(self.width() - 1, 1)
        return max(0.0, min((x - 10) / (w - 20), 1.0)) if w > 20 else 0.0

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._track:
            self._dragging = True
            self._fraction = self._frac_from_pos(int(event.position().x()))
            self.seek_requested.emit(self._fraction)
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = int(event.position().x())
        self._hover_frac = self._frac_from_pos(pos)
        self.setToolTip(self._tooltip_at(self._hover_frac))
        self.update()
        if self._dragging:
            self._fraction = self._hover_frac
            self.seek_requested.emit(self._fraction)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_frac = None
        self.update()

    # ── painting ──────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 10
        bar_y = h // 2 - 8
        bar_h = 16
        bar_x0 = margin
        bar_x1 = w - margin
        bar_w = bar_x1 - bar_x0

        # background
        painter.fillRect(0, 0, w, h, _BG_COLOR)

        if not self._track or not self._track.points:
            painter.setPen(QColor("#888"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No track loaded")
            painter.end()
            return

        # ── track bar ─────────────────────────────────────────────
        painter.fillRect(bar_x0, bar_y, bar_w, bar_h, QColor("#334155"))

        # ── chapters ──────────────────────────────────────────────
        if self._track.chapters:
            total_secs = self._track.duration_seconds or 1
            for ch in self._track.chapters:
                ch_start = ch.start_time if isinstance(ch.start_time, datetime) else None
                ch_end = ch.end_time if isinstance(ch.end_time, datetime) else None
                if ch_start is None:
                    ch_start = self._track.start_time
                if ch_end is None:
                    ch_end = self._track.end_time
                if ch_start is None or ch_end is None:
                    continue
                f0 = (ch_start - self._track.points[0].timestamp).total_seconds() / total_secs
                f1 = (ch_end - self._track.points[0].timestamp).total_seconds() / total_secs
                cx = bar_x0 + int(bar_w * f0)
                cw = max(2, int(bar_w * (f1 - f0)))
                colour = _CHAPTER_COLORS[hash(ch.name or ch.chapter_type) % len(_CHAPTER_COLORS)]
                painter.fillRect(cx, bar_y, cw, bar_h, colour)

        # ── track progress (played portion) ───────────────────────
        played_w = int(bar_w * self._fraction)
        if played_w > 0:
            painter.fillRect(bar_x0, bar_y, played_w, bar_h, _TRACK_COLOR)

        # ── time labels ───────────────────────────────────────────
        painter.setPen(QColor("#aaa"))
        font = QFont("monospace", 9)
        painter.setFont(font)
        start_str = _format_duration(0)
        end_str = _format_duration(self._track.duration_seconds)
        painter.drawText(bar_x0, bar_y + bar_h + 14, start_str)
        painter.drawText(bar_x1 - painter.fontMetrics().horizontalAdvance(end_str),
                         bar_y + bar_h + 14, end_str)

        # ── current time tooltip ──────────────────────────────────
        info_y = 10
        current_secs = self._track.duration_seconds * self._fraction
        time_str = _format_duration(current_secs)
        info_text = f"{time_str}  ({self._fraction * 100:.1f}%)"
        painter.setPen(QColor("#fff"))
        font_b = QFont("monospace", 10)
        font_b.setBold(True)
        painter.setFont(font_b)
        painter.drawText(bar_x0, info_y + 12, info_text)

        # ── playhead ──────────────────────────────────────────────
        ph_x = bar_x0 + int(bar_w * self._fraction)
        painter.setBrush(_PLAYHEAD_COLOR)
        painter.setPen(QPen(QColor("#fff"), 1))
        # triangle above bar
        tri_size = 6.0
        triangle = QPolygonF([
            QPointF(float(ph_x), float(bar_y) - 2.0),
            QPointF(float(ph_x) - tri_size, float(bar_y) - tri_size - 2.0),
            QPointF(float(ph_x) + tri_size, float(bar_y) - tri_size - 2.0),
        ])
        painter.drawPolygon(triangle)
        # vertical line through bar
        painter.setPen(QPen(_PLAYHEAD_COLOR, 2))
        painter.drawLine(ph_x, bar_y, ph_x, bar_y + bar_h)

        # ── hover indicator ───────────────────────────────────────
        if self._hover_frac is not None and not self._dragging:
            hx = bar_x0 + int(bar_w * self._hover_frac)
            painter.setPen(QPen(QColor("#ffffff"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(hx, bar_y, hx, bar_y + bar_h)

        painter.end()

    def _tooltip_at(self, fraction: float) -> str:
        if not self._track or not self._track.points:
            return ""
        secs = self._track.duration_seconds * fraction
        time_str = _format_duration(secs)
        idx = int(fraction * (len(self._track.points) - 1))
        pt = self._track.points[idx]
        return (
            f"{time_str}  |  point {idx:,}/{len(self._track.points):,}\n"
            f"({pt.position.latitude:.5f}, {pt.position.longitude:.5f})"
        )
