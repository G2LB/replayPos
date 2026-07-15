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
    QMenuBar,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from replaypos.importers.csv_wizard import CsvImportWizard
from replaypos.mapping.map_widget import MapWidget
from replaypos.models import Track


class MainWindow(QMainWindow):
    """Main application window for ReplayPos."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ReplayPos")
        self.setMinimumSize(1024, 700)

        self._current_track: Track | None = None

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
        menu_bar: QMenuBar = self.menuBar()

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
        self._play_action.setEnabled(False)

        self._stop_action = toolbar.addAction("\u25A0 Stop")
        self._stop_action.setEnabled(False)

        toolbar.addSeparator()

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(
            ["0.25\u00D7", "0.5\u00D7", "1\u00D7", "2\u00D7", "4\u00D7", "8\u00D7", "16\u00D7"]
        )
        self._speed_combo.setCurrentText("1\u00D7")
        self._speed_combo.setEnabled(False)
        toolbar.addWidget(QLabel(" Speed: "))
        toolbar.addWidget(self._speed_combo)

    # ── dock widgets ──────────────────────────────────────────────

    def _build_docks(self) -> None:
        self._map_dock = QDockWidget("Map", self)
        self._map_dock.setObjectName("MapDock")
        self._map_dock.setWidget(self._map_widget)
        self._map_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._map_dock)

        self._timeline_dock = QDockWidget("Timeline", self)
        self._timeline_dock.setObjectName("TimelineDock")
        self._timeline_container = QWidget()
        self._timeline_layout = QVBoxLayout(self._timeline_container)
        self._timeline_placeholder = QLabel("Timeline — coming soon")
        self._timeline_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timeline_placeholder.setStyleSheet("color: #888;")
        self._timeline_layout.addWidget(self._timeline_placeholder)
        self._timeline_dock.setWidget(self._timeline_container)
        self._timeline_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._timeline_dock)

        # Prevent closing the map dock from hiding the map in the central stack
        self._map_dock.visibilityChanged.connect(self._on_map_visibility_changed)

    # ── status bar ────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        status: QStatusBar = self.statusBar()
        self._status_label = QLabel("Ready")
        status.addPermanentWidget(self._status_label)

    # ── actions ───────────────────────────────────────────────────

    def _on_import_csv(self) -> None:
        wizard = CsvImportWizard(self)
        if wizard.exec() == CsvImportWizard.DialogCode.Accepted and wizard.result_track:
            self._load_track(wizard.result_track)

    def _load_track(self, track: Track) -> None:
        self._current_track = track
        self._map_widget.load_track(track)
        self._map_widget.fit_bounds()
        self._stack.setCurrentWidget(self._map_widget)
        self._update_ui_state()
        pt_count = len(track.points)
        self._status_label.setText(
            f"Track: {track.name or 'Unnamed'} \u2014 {pt_count:,} points"
        )
        logger.info("Loaded track '{}' with {:,} points", track.name, pt_count)

    def _toggle_map(self, visible: bool) -> None:
        self._map_dock.setVisible(visible)
        if visible:
            self._stack.setCurrentWidget(self._map_widget)

    def _toggle_timeline(self, visible: bool) -> None:
        self._timeline_dock.setVisible(visible)

    def _on_map_visibility_changed(self, visible: bool) -> None:
        self._show_map_action.setChecked(visible)
        if visible:
            self._stack.setCurrentWidget(self._map_widget)
        else:
            self._stack.setCurrentWidget(self._empty_label)

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
