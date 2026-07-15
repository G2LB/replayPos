from __future__ import annotations

import sys
from datetime import date, timedelta

from loguru import logger
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from replaypos.importers.csv_wizard import CsvImportWizard
from replaypos.mapping.map_widget import MapWidget
from replaypos.models import Track, TrackPoint
from replaypos.playback import PlaybackController
from replaypos.timeline import TimelineWidget
from replaypos.ui.day_filter import DayFilterWidget
from replaypos.ui.nerd_font import init_nerd_fonts, nerd_icon


class MainWindow(QMainWindow):
    """Main application window for ReplayPos."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ReplayPos")
        self.setMinimumSize(1024, 700)

        self._full_track: Track | None = None  # original unfiltered track
        self._current_track: Track | None = None  # currently displayed (may be filtered)
        self._current_interval_idx: int = 0  # index into the 6-min interval list
        self._interval_list: list[dict] = []  # cached intervals for the active filter

        self._playback = PlaybackController(self)
        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.playing_changed.connect(self._on_playing_changed)

        self._build_central_widget()
        self._build_menu_bar()
        self._build_toolbar()
        self._build_docks()
        self._build_status_bar()
        self._update_ui_state()

    # ── central widget ────────────────────────────────────────────

    def _build_central_widget(self) -> None:
        self._stack = QStackedWidget()
        self._empty_label = QLabel("Open a project or import a CSV file to get started.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #888; font-size: 16px; padding: 40px;")
        self._map_widget = MapWidget()
        self._stack.addWidget(self._empty_label)
        self._stack.addWidget(self._map_widget)
        self._stack.setCurrentWidget(self._empty_label)
        self.setCentralWidget(self._stack)

    # ── menu bar ──────────────────────────────────────────────────

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        import_action = QAction("Import &CSV...", self)
        import_action.setIcon(nerd_icon("nf-fae-file_import", color="#4ade80"))
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._on_import_csv)
        file_menu.addAction(import_action)

        export_action = QAction("&Export to Database...", self)
        export_action.setIcon(nerd_icon("nf-md-database_export", color="#fbbf24"))
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._on_export_db)
        export_action.setEnabled(False)
        self._export_action = export_action
        export_action.triggered.connect(self._on_export_db)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("&View")

        self._show_map_action = QAction("&Map", self)
        self._show_map_action.setCheckable(True)
        self._show_map_action.setChecked(True)
        self._show_map_action.triggered.connect(self._toggle_map)
        view_menu.addAction(self._show_map_action)

        self._show_timeline_action = QAction("&Timeline", self)
        self._show_timeline_action.setCheckable(True)
        self._show_timeline_action.setChecked(True)
        self._show_timeline_action.triggered.connect(self._toggle_timeline)
        view_menu.addAction(self._show_timeline_action)

        view_menu.addSeparator()

        self._show_openseamap_action = QAction("OpenSeaMap &Overlay", self)
        self._show_openseamap_action.setCheckable(True)
        self._show_openseamap_action.setChecked(True)
        self._show_openseamap_action.triggered.connect(self._toggle_openseamap)
        view_menu.addAction(self._show_openseamap_action)

        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    # ── toolbar ───────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar: QToolBar = self.addToolBar("Playback")
        toolbar.setObjectName("PlaybackToolbar")
        toolbar.setMovable(False)

        play_icon = nerd_icon("nf-md-play", size=20, color="#4ade80")
        self._play_action = toolbar.addAction(play_icon, "Play")
        self._play_action.triggered.connect(self._on_play_pause)
        self._play_action.setEnabled(False)

        stop_icon = nerd_icon("nf-md-stop", size=20, color="#ef4444")
        self._stop_action = toolbar.addAction(stop_icon, "Stop")
        self._stop_action.triggered.connect(self._on_stop)
        self._stop_action.setEnabled(False)

        toolbar.addSeparator()

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(
            [
                "0.25\u00d7", "0.5\u00d7", "1\u00d7", "2\u00d7",
                "4\u00d7", "8\u00d7", "16\u00d7", "60\u00d7", "120\u00d7",
            ]
        )
        self._speed_combo.setCurrentText("1\u00d7")
        self._speed_combo.currentTextChanged.connect(self._on_speed_changed)
        self._speed_combo.setEnabled(False)
        toolbar.addWidget(QLabel(" Speed: "))
        toolbar.addWidget(self._speed_combo)

        # ── fit-to-track button ──
        toolbar.addSeparator()
        fit_icon = nerd_icon("nf-md-map_marker", size=20, color="#60a5fa")
        self._fit_action = toolbar.addAction(fit_icon, "Fit")
        self._fit_action.triggered.connect(self._on_fit_track)
        self._fit_action.setEnabled(False)

        # ── day filter ──
        toolbar.addSeparator()
        self._day_filter = DayFilterWidget()
        self._day_filter.selection_changed.connect(self._on_day_filter_changed)
        toolbar.addWidget(self._day_filter)

    # ── dock widgets ──────────────────────────────────────────────

    def _build_docks(self) -> None:
        # Map lives in the central QStackedWidget (not in a dock) so the
        # stack always owns it.  The timeline is the only dock widget.
        self._timeline_dock = QDockWidget("Timeline", self)
        self._timeline_dock.setObjectName("TimelineDock")
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        self._timeline_widget = TimelineWidget()
        self._timeline_widget.seek_requested.connect(self._on_timeline_seek)
        layout.addWidget(self._timeline_widget)
        self._timeline_dock.setWidget(container)
        self._timeline_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._timeline_dock)

    # ── status bar ────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        status: QStatusBar = self.statusBar()
        self._status_label = QLabel("Ready")
        status.addPermanentWidget(self._status_label)

    # ── file actions ──────────────────────────────────────────────

    def _on_import_csv(self) -> None:
        wizard = CsvImportWizard(self)
        if wizard.exec() == CsvImportWizard.DialogCode.Accepted and wizard.result_track:
            self._load_track(wizard.result_track)

    def _load_track(self, track: Track) -> None:
        self._full_track = track

        # Load ALL days into the map as separate JS layers
        self._map_widget.load_track(track)
        self._map_widget.fit_bounds()
        self._stack.setCurrentWidget(self._map_widget)

        # Populate the day filter widget
        counts: dict[date, int] = {}
        for p in track.points:
            d = p.timestamp.date()
            counts[d] = counts.get(d, 0) + 1
        stationary = track.stationary_dates
        self._day_filter.load_dates(track.unique_dates, stationary, counts)

        # Apply initial filter (all moving days selected by default)
        self._on_day_filter_changed()

    def _on_day_filter_changed(self) -> None:
        """Respond to day-filter changes (fast path: JS layer toggle only)."""
        if not self._full_track:
            return
        selected = set(self._day_filter.selected_dates())

        # 1. Toggle day layers in JS — instant, no GeoJSON transfer
        for d in self._full_track.unique_dates:
            iso = d.isoformat()
            self._map_widget.set_day_visible(iso, iso in selected)

        # 2. Update playback + timeline with the filtered point set
        if not selected:
            empty = self._full_track.model_copy(update={"points": [], "chapters": [], "events": []})
            self._apply_filtered_track(empty, reload_map=False)
            return

        try:
            targets = {date.fromisoformat(s) for s in selected}
            filtered = self._full_track.filter_by_dates(targets)
            self._apply_filtered_track(filtered, reload_map=False)
        except ValueError:
            pass

    @staticmethod
    def _compute_intervals(track: Track, interval_minutes: int = 6) -> list[dict]:
        """Find track points at *interval_minutes* time intervals.

        Returns a list of ``{"coords": [lng, lat], "time": str, "point_idx": int}``.
        """
        if not track.points:
            return []
        intervals: list[dict] = []
        secs = interval_minutes * 60
        start = track.points[0].timestamp
        next_mark = start + timedelta(seconds=secs)

        for pt in track.points:
            if pt.timestamp >= next_mark:
                intervals.append(
                    {
                        "coords": [pt.position.longitude, pt.position.latitude],
                        "time": pt.timestamp.isoformat(timespec="minutes"),
                        "point_idx": pt.index,
                    }
                )
                next_mark += timedelta(seconds=secs)
        return intervals

    def _apply_filtered_track(self, track: Track, reload_map: bool = False) -> None:
        """Load *track* into playback and timeline.

        Parameters
        ----------
        track :
            The (possibly filtered) track to use.
        reload_map :
            If True, also reload the full GeoJSON into the map
            (used only on initial load; day toggles skip this).
        """
        self._current_track = track
        self._current_interval_idx = 0
        self._interval_list = self._compute_intervals(track)

        self._playback.load_track(track)
        self._timeline_widget.load_track(track)
        self._timeline_widget.load_intervals(self._interval_list)
        self._map_widget.load_intervals(self._interval_list)
        self._map_widget.reset_progress()
        if reload_map:
            self._map_widget.load_track(track)
            self._map_widget.fit_bounds()
        self._update_ui_state()
        pt_count = len(track.points)
        self._status_label.setText(f"Track: {track.name or 'Unnamed'} \u2014 {pt_count:,} points")
        logger.info("Loaded track '{}' with {:,} points", track.name, pt_count)

    # ── playback actions ──────────────────────────────────────────

    def _on_play_pause(self) -> None:
        if self._playback.is_playing:
            self._playback.pause()
        else:
            self._playback.play()

    def _on_stop(self) -> None:
        self._playback.stop()

    def _on_speed_changed(self, text: str) -> None:
        speed_str = text.replace("\u00d7", "").strip()
        try:
            speed = float(speed_str)
            self._playback.set_speed(speed)
        except ValueError:
            pass

    def _on_fit_track(self) -> None:
        """Re-center the map on the current track."""
        self._map_widget.fit_bounds()

    def _on_timeline_seek(self, fraction: float) -> None:
        self._playback.seek_to_position(fraction)

    def _on_position_changed(self, point: TrackPoint) -> None:
        """Update map highlight, progress trail, timer, and timeline when playback advances."""
        self._map_widget.highlight_point(point)
        self._map_widget.append_progress_point([point.position.longitude, point.position.latitude])
        self._map_widget.set_time_display(point.timestamp.isoformat(timespec="seconds"))

        # Advance interval marker if we've passed the next interval point
        if self._interval_list and self._current_interval_idx < len(self._interval_list):
            next_iv = self._interval_list[self._current_interval_idx]
            idx = self._playback.current_index
            if idx >= next_iv["point_idx"]:
                self._map_widget.highlight_interval(next_iv["coords"])
                self._timeline_widget.set_current_interval(self._current_interval_idx)
                self._current_interval_idx += 1

        if self._current_track and self._current_track.points:
            total = len(self._current_track.points) - 1
            idx = self._playback.current_index
            self._timeline_widget.set_position(idx / max(total, 1))
            self._status_label.setText(
                f"Point {idx:,}/{len(self._current_track.points):,}  "
                f"({point.position.latitude:.5f}, {point.position.longitude:.5f})"
            )

    def _on_export_db(self) -> None:
        """Export the current track to the database (placeholder)."""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.information(
            self,
            "Export to Database",
            "Database export is not yet implemented.",
        )

    def _on_playing_changed(self, playing: bool) -> None:
        self._play_action.setText("Pause" if playing else "Play")
        self._play_action.setIcon(
            nerd_icon("nf-md-pause", size=20, color="#fbbf24" if playing else "#4ade80")
        )

    # ── view actions ──────────────────────────────────────────────

    def _toggle_map(self, visible: bool) -> None:
        if visible:
            self._stack.setCurrentWidget(self._map_widget)
        elif self._current_track:
            self._stack.setCurrentWidget(self._empty_label)

    def _toggle_timeline(self, visible: bool) -> None:
        self._timeline_dock.setVisible(visible)

    def _toggle_openseamap(self, visible: bool) -> None:
        self._map_widget.set_openseamap_visible(visible)

    def _on_about(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            "About ReplayPos",
            "ReplayPos v0.1.0\n\n"
            "GIS-based replay, analysis and reporting platform\n"
            "for mobile objects (vessels, vehicles, machinery).",
        )

    def _update_ui_state(self) -> None:
        has_track = self._current_track is not None
        self._play_action.setEnabled(has_track)
        self._stop_action.setEnabled(has_track)
        self._speed_combo.setEnabled(has_track)
        self._fit_action.setEnabled(has_track)
        self._export_action.setEnabled(has_track)


def main() -> None:
    """Application entry point — create QApplication, show MainWindow, run event loop."""
    # Must be set before QApplication to allow QWebEngineView import
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("ReplayPos")
    app.setOrganizationName("ReplayPos")

    # Load Nerd Fonts for UI icons (downloads + caches on first run)
    init_nerd_fonts()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
