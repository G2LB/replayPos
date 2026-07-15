from __future__ import annotations

import sys

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


class MainWindow(QMainWindow):
    """Main application window for ReplayPos."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ReplayPos")
        self.setMinimumSize(1024, 700)

        self._full_track: Track | None = None     # original unfiltered track
        self._current_track: Track | None = None  # currently displayed (may be filtered)

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
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._on_import_csv)
        file_menu.addAction(import_action)

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

        self._play_action = toolbar.addAction("\u25B6 Play")
        self._play_action.triggered.connect(self._on_play_pause)
        self._play_action.setEnabled(False)

        self._stop_action = toolbar.addAction("\u25A0 Stop")
        self._stop_action.triggered.connect(self._on_stop)
        self._stop_action.setEnabled(False)

        toolbar.addSeparator()

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(
            ["0.25\u00D7", "0.5\u00D7", "1\u00D7", "2\u00D7", "4\u00D7", "8\u00D7", "16\u00D7"]
        )
        self._speed_combo.setCurrentText("1\u00D7")
        self._speed_combo.currentTextChanged.connect(self._on_speed_changed)
        self._speed_combo.setEnabled(False)
        toolbar.addWidget(QLabel(" Speed: "))
        toolbar.addWidget(self._speed_combo)

        # ── fit-to-track button ──
        toolbar.addSeparator()
        self._fit_action = toolbar.addAction("\U0001F30D Fit")
        self._fit_action.triggered.connect(self._on_fit_track)
        self._fit_action.setEnabled(False)

        # ── day filter ──
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Day: "))
        self._day_combo = QComboBox()
        self._day_combo.setMinimumWidth(110)
        self._day_combo.currentTextChanged.connect(self._on_day_changed)
        self._day_combo.setEnabled(False)
        toolbar.addWidget(self._day_combo)

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
        self._populate_day_combo(track)
        # Apply the currently selected day filter (default: first day)
        if self._day_combo.count() > 1:
            self._on_day_changed(self._day_combo.currentText())
        else:
            self._apply_filtered_track(track)

    def _populate_day_combo(self, track: Track) -> None:
        """Fill the day combo with unique dates from *track* plus an 'All dates' entry."""
        self._day_combo.blockSignals(True)
        self._day_combo.clear()
        self._day_combo.addItem("All dates")
        for d in track.unique_dates:
            self._day_combo.addItem(d.isoformat())
        self._day_combo.blockSignals(False)
        self._day_combo.setCurrentIndex(self._day_combo.count() > 1)  # select first date if any

    def _on_day_changed(self, text: str) -> None:
        """Filter the track to the selected day and reload all views."""
        if not self._full_track:
            return
        if text == "All dates" or not text:
            self._apply_filtered_track(self._full_track)
        else:
            try:
                filtered = self._full_track.filter_by_date(text)
                self._apply_filtered_track(filtered)
            except ValueError:
                pass

    def _apply_filtered_track(self, track: Track) -> None:
        """Reload map, timeline and playback with the given (possibly filtered) track."""
        self._current_track = track
        self._playback.load_track(track)
        self._map_widget.load_track(track)
        self._map_widget.fit_bounds()
        self._timeline_widget.load_track(track)
        self._stack.setCurrentWidget(self._map_widget)
        self._update_ui_state()
        pt_count = len(track.points)
        self._status_label.setText(
            f"Track: {track.name or 'Unnamed'} \u2014 {pt_count:,} points"
        )
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
        speed_str = text.replace("\u00D7", "").strip()
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
        """Update map highlight and timeline when playback advances."""
        self._map_widget.highlight_point(point)
        if self._current_track and self._current_track.points:
            total = len(self._current_track.points) - 1
            idx = self._playback.current_index
            self._timeline_widget.set_position(idx / max(total, 1))
            self._status_label.setText(
                f"Point {idx:,}/{len(self._current_track.points):,}  "
                f"({point.position.latitude:.5f}, {point.position.longitude:.5f})"
            )

    def _on_playing_changed(self, playing: bool) -> None:
        self._play_action.setText("\u23F8 Pause" if playing else "\u25B6 Play")

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
        self._day_combo.setEnabled(has_track and self._day_combo.count() > 1)


def main() -> None:
    """Application entry point — create QApplication, show MainWindow, run event loop."""
    # Must be set before QApplication to allow QWebEngineView import
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("ReplayPos")
    app.setOrganizationName("ReplayPos")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
