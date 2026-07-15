from __future__ import annotations

import csv
from pathlib import Path

from loguru import logger
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from replaypos.importers.csv_filter import FilterConfig, FilterEngine
from replaypos.importers.csv_importer import (
    CsvColumnMapper,
    CsvReader,
    TemplateManager,
    TrackPointBuilder,
    detect_delimiter,
)
from replaypos.models import Project, Track

ALL_FIELDS = [
    ("timestamp", "Timestamp *", True),
    ("utm_easting", "UTM Easting", False),
    ("utm_northing", "UTM Northing", False),
    ("utm_zone", "UTM Zone", False),
    ("latitude", "Latitude", False),
    ("longitude", "Longitude", False),
    ("elevation", "Elevation (Z)", False),
    ("sog", "SOG", False),
    ("cog", "COG", False),
    ("heading", "Heading", False),
    ("speed", "Speed", False),
    ("gps_accuracy", "GPS Accuracy", False),
    ("gps_satellites", "GPS Satellites", False),
    ("gps_fix_quality", "GPS Fix Quality", False),
    ("ukc_front", "UKC Front", False),
    ("ukc_aft", "UKC Aft", False),
    ("tide", "Tide", False),
    ("water_level", "Water Level", False),
]

TIMESTAMP_FORMAT_ITEMS = [
    ("HH:MM:SS DD-MM-YYYY", "%H:%M:%S %d-%m-%Y"),
    ("DD-MM-YYYY HH:MM:SS", "%d-%m-%Y %H:%M:%S"),
    ("ISO 8601", "%Y-%m-%dT%H:%M:%S"),
    ("YYYY-MM-DD HH:MM:SS", "%Y-%m-%d %H:%M:%S"),
    ("Auto-detect", ""),
]


class PageFileSelect(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Select CSV File")
        self.setSubTitle("Choose a CSV file to import and preview its contents.")

        layout = QVBoxLayout()

        file_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select a CSV file...")
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self.file_path)
        file_row.addWidget(self.browse_btn)
        layout.addLayout(file_row)

        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems(
            ["Comma (,)", "Semicolon (;)", "Tab", "Pipe (|)", "Auto-detect"]
        )
        self.delimiter_combo.currentTextChanged.connect(self._refresh_preview)
        layout.addWidget(QLabel("Delimiter:"))
        layout.addWidget(self.delimiter_combo)

        self.table = QTableWidget()
        self.table.setMinimumHeight(200)
        layout.addWidget(QLabel("Preview (first 10 rows):"))
        layout.addWidget(self.table)

        self.setLayout(layout)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", "", "CSV files (*.csv);;All files (*)"
        )
        if path:
            self.file_path.setText(path)
            self._refresh_preview()

    def _refresh_preview(self):
        path = self.file_path.text().strip()
        if not path or not Path(path).exists():
            return
        try:
            delim_text = self.delimiter_combo.currentText()
            if delim_text == "Auto-detect":
                delimiter = detect_delimiter(path)
            else:
                delim_map = {"Comma (,)": ",", "Semicolon (;)": ";", "Tab": "\t", "Pipe (|)": "|"}
                delimiter = delim_map.get(delim_text, ",")

            headers, rows = [], []
            with open(path, newline="") as f:
                reader = csv.reader(f, delimiter=delimiter)
                headers = next(reader)
                for i, row in enumerate(reader):
                    if i >= 10:
                        break
                    rows.append(row)

            self.table.clear()
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    self.table.setItem(r, c, QTableWidgetItem(val))
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        except Exception as e:
            logger.warning("Preview failed: {}", e)

    def get_file_info(self) -> dict:
        path = self.file_path.text().strip()
        delim_text = self.delimiter_combo.currentText()
        if delim_text == "Auto-detect":
            delimiter = detect_delimiter(path)
        else:
            delim_map = {"Comma (,)": ",", "Semicolon (;)": ";", "Tab": "\t", "Pipe (|)": "|"}
            delimiter = delim_map.get(delim_text, ",")
        return {"path": path, "delimiter": delimiter}


# ── colour helpers ───────────────────────────────────────────────

_DOT_GREEN = "#22c55e"   # required + mapped
_DOT_BLUE = "#3b82f6"    # optional + mapped
_DOT_GRAY = "#9ca3af"    # not mapped
_DOT_RED = "#ef4444"     # required + not mapped


class _DotLabel(QLabel):
    """Small coloured circle indicator for field mapping status."""

    def __init__(self, colour: str = _DOT_GRAY) -> None:
        super().__init__()
        self.setFixedSize(14, 14)
        self._colour = colour
        self._update_style()

    def set_colour(self, colour: str) -> None:
        if colour != self._colour:
            self._colour = colour
            self._update_style()

    def _update_style(self) -> None:
        self.setStyleSheet(
            f"background-color: {self._colour};"
            "border-radius: 7px;"
            "min-width: 14px; min-height: 14px;"
        )


class _FieldRow(QWidget):
    """One row in the column mapping: dot + label + combo."""

    def __init__(
        self,
        field_key: str,
        field_label: str,
        required: bool,
        on_changed: callable,
    ) -> None:
        super().__init__()
        self.field_key = field_key
        self.required = required
        self._on_changed = on_changed

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self.dot = _DotLabel()
        layout.addWidget(self.dot)

        label = QLabel(field_label)
        if required:
            bold_font = QFont()
            bold_font.setBold(True)
            label.setFont(bold_font)
        label.setMinimumWidth(130)
        layout.addWidget(label)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(200)
        self.combo.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo, 1)

        self.status_label = QLabel()
        self.status_label.setMinimumWidth(80)
        layout.addWidget(self.status_label)

        self._update_status()

    def _on_combo_changed(self, text: str) -> None:
        self._update_status()
        self._on_changed()

    def _update_status(self) -> None:
        text = self.combo.currentText()
        mapped = text and text != "-- none --"

        if self.required and not mapped:
            self.dot.set_colour(_DOT_RED)
            self.status_label.setText("required")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 11px;")
        elif self.required and mapped:
            self.dot.set_colour(_DOT_GREEN)
            self.status_label.setText("OK")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 11px;")
        elif mapped:
            self.dot.set_colour(_DOT_BLUE)
            self.status_label.setText("")
            self.status_label.setStyleSheet("")
        else:
            self.dot.set_colour(_DOT_GRAY)
            self.status_label.setText("")
            self.status_label.setStyleSheet("")


class PageColumnMapping(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Column Mapping")
        self.setSubTitle(
            "Map CSV columns to ReplayPos fields. "
            "\U0001f7e2 required mapped  \U0001f7e5 required missing  "
            "\U0001f535 optional mapped  \u26aa optional"
        )

        self._rows: list[_FieldRow] = []

        layout = QVBoxLayout()

        # ── template bar ──────────────────────────────────────────
        template_row = QHBoxLayout()
        self.template_combo = QComboBox()
        self.template_combo.currentIndexChanged.connect(self._apply_template)
        self.save_template_btn = QPushButton("Save as template")
        self.save_template_btn.clicked.connect(self._save_template)
        template_row.addWidget(QLabel("Template:"))
        template_row.addWidget(self.template_combo, 1)
        template_row.addWidget(self.save_template_btn)
        layout.addLayout(template_row)

        # ── separator ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── scrollable field rows ─────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._fields_container = QWidget()
        fields_layout = QVBoxLayout(self._fields_container)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(2)

        for field_key, field_label, required in ALL_FIELDS:
            row = _FieldRow(field_key, field_label, required, self._on_row_changed)
            self._rows.append(row)
            fields_layout.addWidget(row)

        fields_layout.addStretch()
        scroll.setWidget(self._fields_container)
        layout.addWidget(scroll)

        self.setLayout(layout)

    def initializePage(self) -> None:  # noqa: N802
        wizard = self.wizard()
        if not wizard or not hasattr(wizard, "file_info"):
            return
        file_info = wizard.file_info
        if not file_info or not file_info.get("path"):
            return
        path = file_info["path"]
        delimiter = file_info["delimiter"]

        headers: list[str] = []
        try:
            with open(path, newline="") as f:
                reader = csv.reader(f, delimiter=delimiter)
                headers = next(reader)
        except Exception:
            return

        blank = ["-- none --"] + headers
        for row in self._rows:
            current = row.combo.currentText()
            row.combo.blockSignals(True)
            row.combo.clear()
            row.combo.addItems(blank)
            if current in blank:
                row.combo.setCurrentText(current)
            row.combo.blockSignals(False)
            row._update_status()

        self._refresh_templates()

    def _refresh_templates(self) -> None:
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem("-- Manual mapping --")
        for tpl in TemplateManager.list_templates():
            self.template_combo.addItem(tpl["name"])
        self.template_combo.blockSignals(False)

    def _apply_template(self, index: int) -> None:
        name = self.template_combo.currentText()
        if name == "-- Manual mapping --":
            return
        tpl = TemplateManager.load_template(name)
        if not tpl:
            return
        mapping = tpl.get("mapping", {})
        for row in self._rows:
            col_name = mapping.get(row.field_key)
            if col_name:
                idx = row.combo.findText(col_name)
                if idx >= 0:
                    row.combo.setCurrentIndex(idx)

    def _save_template(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Template", "Template name:")
        if not ok or not name.strip():
            return
        mapping = {}
        for row in self._rows:
            val = row.combo.currentText()
            if val and val != "-- none --":
                mapping[row.field_key] = val
        TemplateManager.save_template(name.strip(), mapping)
        self._refresh_templates()

    def _on_row_changed(self) -> None:
        """Called whenever any combo changes — updates wizard completeness."""
        self.completeChanged.emit()

    def isComplete(self) -> bool:  # noqa: N802
        """Wizard can advance only when the required field is mapped."""
        for row in self._rows:
            if row.required:
                text = row.combo.currentText()
                if not text or text == "-- none --":
                    return False
        return True

    def get_mapping(self) -> dict[str, str]:
        mapping = {}
        for row in self._rows:
            val = row.combo.currentText()
            if val and val != "-- none --":
                mapping[row.field_key] = val
        return mapping


class PageFilter(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Filter Options")
        self.setSubTitle("Configure stationary detection and filtering.")

        layout = QVBoxLayout()

        self.enable_filter = QCheckBox("Filter stationary periods")
        self.enable_filter.setChecked(True)
        layout.addWidget(self.enable_filter)

        grid = QGroupBox("Stationary Detection")
        grid_layout = QFormLayout()

        self.sog_slider = QSlider(Qt.Orientation.Horizontal)
        self.sog_slider.setRange(1, 50)
        self.sog_slider.setValue(5)
        self.sog_label = QLabel("0.5 kn")
        self.sog_slider.valueChanged.connect(
            lambda v: self.sog_label.setText(f"{v / 10:.1f} kn")
        )
        sog_row = QHBoxLayout()
        sog_row.addWidget(self.sog_slider)
        sog_row.addWidget(self.sog_label)
        grid_layout.addRow("SOG threshold:", sog_row)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 600)
        self.duration_spin.setValue(60)
        self.duration_spin.setSuffix(" sec")
        grid_layout.addRow("Min stop duration:", self.duration_spin)

        self.trim_leading = QCheckBox("Trim leading stationary")
        self.trim_leading.setChecked(True)
        grid_layout.addRow(self.trim_leading)

        self.trim_trailing = QCheckBox("Trim trailing stationary")
        self.trim_trailing.setChecked(True)
        grid_layout.addRow(self.trim_trailing)

        self.create_chapters = QCheckBox("Create chapters for stops")
        self.create_chapters.setChecked(True)
        grid_layout.addRow(self.create_chapters)

        self.use_cog = QCheckBox("Use COG detection (recommended)")
        self.use_cog.setChecked(True)
        grid_layout.addRow(self.use_cog)

        grid.setLayout(grid_layout)
        layout.addWidget(grid)

        preview_group = QGroupBox("Filter Preview")
        preview_layout = QVBoxLayout()
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        preview_layout.addWidget(self.preview_text)
        self.preview_btn = QPushButton("Estimate reduction")
        self.preview_btn.clicked.connect(self._update_preview)
        preview_layout.addWidget(self.preview_btn)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        layout.addStretch()
        self.setLayout(layout)
        self._points_for_preview: list = []

    def set_preview_points(self, points: list):
        self._points_for_preview = points

    def _update_preview(self):
        if not self._points_for_preview:
            self.preview_text.setText("No data loaded yet. Complete mapping first.")
            return
        engine = FilterEngine(self.get_filter_config())
        estimate = engine.estimate_reduction(self._points_for_preview)
        self.preview_text.setText(
            f"Total: {estimate['total']:,} pts\n"
            f"After filter: {estimate['kept']:,} pts "
            f"({estimate['reduction_pct']}% reduction)\n"
            f"Stops found: {estimate['stops_found']}\n"
            f"Stop chapters: {estimate['stop_chapters']}"
        )

    def get_filter_config(self) -> FilterConfig:
        return FilterConfig(
            sog_threshold=self.sog_slider.value() / 10.0,
            min_stop_seconds=self.duration_spin.value(),
            trim_leading=self.trim_leading.isChecked(),
            trim_trailing=self.trim_trailing.isChecked(),
            create_stop_chapters=self.create_chapters.isChecked(),
            use_cog_detection=self.use_cog.isChecked(),
        )

    def is_filter_enabled(self) -> bool:
        return self.enable_filter.isChecked()


class PageMetadata(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Track Metadata")
        self.setSubTitle("Set the track name and select a project.")

        layout = QFormLayout()

        self.track_name = QLineEdit()
        self.track_name.setPlaceholderText("Auto from filename")
        layout.addRow("Track name:", self.track_name)

        self.project_combo = QComboBox()
        self.project_combo.setEditable(True)
        self.project_combo.setPlaceholderText("Select or type new project name...")
        layout.addRow("Project:", self.project_combo)

        self.project_client = QLineEdit()
        self.project_client.setPlaceholderText("Optional")
        layout.addRow("Client:", self.project_client)

        self.fmt_combo = QComboBox()
        for label, _ in TIMESTAMP_FORMAT_ITEMS:
            self.fmt_combo.addItem(label)
        self.fmt_combo.setCurrentText("Auto-detect")
        layout.addRow("Timestamp format:", self.fmt_combo)

        self.setLayout(layout)

    def initializePage(self):  # noqa: N802
        wizard = self.wizard()
        if wizard and hasattr(wizard, "file_info") and wizard.file_info:
            path = Path(wizard.file_info["path"])
            self.track_name.setText(path.stem)

        self._refresh_projects()

    def _refresh_projects(self):
        try:
            from replaypos.database.database import get_database
            from replaypos.database.repository import ProjectRepository
            db = get_database()
            with db.create_session() as session:
                repo = ProjectRepository(session)
                projects = repo.list_all()
                self.project_combo.clear()
                self.project_combo.addItem("-- New project --")
                for p in projects:
                    self.project_combo.addItem(p.name)
        except Exception:
            self.project_combo.clear()
            self.project_combo.addItem("-- New project --")

    def get_metadata(self) -> dict:
        fmt_label = self.fmt_combo.currentText()
        fmt = ""
        for label, f in TIMESTAMP_FORMAT_ITEMS:
            if label == fmt_label:
                fmt = f
                break
        return {
            "track_name": self.track_name.text().strip() or "Imported Track",
            "project_name": self.project_combo.currentText(),
            "project_client": self.project_client.text().strip(),
            "timestamp_fmt": fmt,
        }


class PageImportProgress(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Import Progress")
        self.setSubTitle("Importing and processing data...")

        layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

        self.setLayout(layout)

    def initializePage(self):  # noqa: N802
        self.progress_bar.setValue(0)
        self.status_text.clear()
        wizard = self.wizard()
        if hasattr(wizard, "run_import"):
            wizard.run_import()


class CsvImportWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CSV Import Wizard")
        self.setMinimumSize(700, 600)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.file_info: dict = {}
        self.mapping: dict[str, str] = {}
        self.result_track: Track | None = None

        self.page_file = PageFileSelect()
        self.page_mapping = PageColumnMapping()
        self.page_filter = PageFilter()
        self.page_metadata = PageMetadata()
        self.page_progress = PageImportProgress()

        self.addPage(self.page_file)
        self.addPage(self.page_mapping)
        self.addPage(self.page_filter)
        self.addPage(self.page_metadata)
        self.addPage(self.page_progress)

        self.currentIdChanged.connect(self._on_page_change)

    def _on_page_change(self, page_id: int):
        if page_id == 1:
            # Populate file_info before ColumnMapping page initializes
            self.file_info = self.page_file.get_file_info()
        elif page_id == 3:
            self._load_preview_points()

    def _load_preview_points(self):
        mapping = self.page_mapping.get_mapping()
        if not mapping.get("timestamp"):
            return
        file_info = self.page_file.get_file_info()
        try:
            mapper = CsvColumnMapper(mapping)
            reader = CsvReader(
                file_info["path"],
                mapper,
                delimiter=file_info["delimiter"],
            )
            builder = TrackPointBuilder()
            preview = reader.read_all(builder)[:500]
            self.page_filter.set_preview_points(preview)
        except Exception as e:
            logger.warning("Preview load failed: {}", e)

    def run_import(self):
        try:
            file_info = self.page_file.get_file_info()
            mapping = self.page_mapping.get_mapping()
            metadata = self.page_metadata.get_metadata()
            filter_config = self.page_filter.get_filter_config()
            do_filter = self.page_filter.is_filter_enabled()

            self.page_progress.status_text.append("Parsing CSV...")
            self.page_progress.progress_bar.setValue(10)

            mapper = CsvColumnMapper(mapping)
            reader = CsvReader(
                file_info["path"],
                mapper,
                timestamp_fmt=metadata["timestamp_fmt"],
                delimiter=file_info["delimiter"],
            )
            builder = TrackPointBuilder(timestamp_fmt=metadata["timestamp_fmt"])

            def progress_cb(current: int, total: int):
                if total > 0:
                    pct = 10 + int(40 * current / total)
                    self.page_progress.progress_bar.setValue(min(pct, 50))

            raw_points = reader.read_all(builder, progress=progress_cb)
            self.page_progress.status_text.append(f"Parsed {len(raw_points):,} raw points")
            self.page_progress.progress_bar.setValue(50)

            if do_filter:
                self.page_progress.status_text.append("Filtering stationary periods...")
                engine = FilterEngine(filter_config)
                result = engine.detect_stops(raw_points)

                track = Track(
                    name=metadata["track_name"],
                    source_file=file_info["path"],
                    points=result.filtered_points,
                    chapters=result.stop_chapters if filter_config.create_stop_chapters else [],
                )
                self.page_progress.status_text.append(
                    f"Filtered: {result.kept_count:,} kept, "
                    f"{result.removed_count:,} removed "
                    f"({len(result.stop_chapters)} stop chapters)"
                )
            else:
                track = Track(
                    name=metadata["track_name"],
                    source_file=file_info["path"],
                    points=raw_points,
                )
                self.page_progress.status_text.append("No filtering applied")

            self.page_progress.progress_bar.setValue(70)

            project_name = metadata["project_name"]
            if project_name and project_name != "-- New project --":
                from replaypos.database.database import get_database
                from replaypos.database.repository import (
                    ProjectRepository,
                    TrackRepository,
                )

                db = get_database()
                with db.create_session() as session:
                    proj_repo = ProjectRepository(session)
                    projects = proj_repo.list_all()
                    project = None
                    for p in projects:
                        if p.name == project_name:
                            project = p
                            break

                    if project is None:
                        project = Project(
                            name=project_name,
                            client=metadata.get("project_client") or None,
                        )
                        proj_repo.create(project)

                    track_repo = TrackRepository(session)
                    track_repo.save(track, project.id)

                self.page_progress.status_text.append(
                    f"Saved to project '{project_name}' ({len(track.points):,} pts)"
                )

            self.result_track = track
            self.page_progress.progress_bar.setValue(100)
            self.page_progress.status_text.append("Import complete!")

        except Exception as e:
            logger.error("Import failed: {}", e)
            self.page_progress.status_text.append(f"ERROR: {e}")
            self.page_progress.progress_bar.setValue(0)
