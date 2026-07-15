from __future__ import annotations

from datetime import date

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QToolButton, QWidget


class DayFilterWidget(QWidget):
    """Toolbar widget with a dropdown menu of checkable date entries.

    Features
    --------
    - ``All dates`` master toggle
    - ``Hide stationary days`` toggle (default ON)
    - One checkable row per date; stationary dates are *italicised*
      and hidden when the stationary toggle is ON.
    - ``selection_changed`` signal emitted whenever any checkbox or
      the stationary toggle changes.
    """

    selection_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._date_actions: list[QAction] = []
        self._stationary_set: set[str] = set()  # ISO date strings

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._button = QToolButton()
        self._button.setText("\U0001F4C5 Day filter \u25BE")
        self._button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._menu = QMenu(self._button)
        self._button.setMenu(self._menu)
        layout.addWidget(self._button)

        self._summary = QLabel("")
        layout.addWidget(self._summary)

        self._all_action: QAction | None = None
        self._hide_st_action: QAction | None = None

    # ── public API ────────────────────────────────────────────────

    def load_dates(
        self,
        dates: list[date],
        stationary: set[date],
        point_counts: dict[date, int] | None = None,
    ) -> None:
        """Populate the menu with date entries.

        Parameters
        ----------
        dates :
            Sorted unique dates in the track.
        stationary :
            Subset of *dates* that are considered stationary.
        point_counts :
            Optional ``{date: point_count}`` shown in the row label.
        """
        self._menu.clear()
        self._date_actions.clear()
        self._stationary_set = {d.isoformat() for d in stationary}
        counts: dict[str, int] = (
            {d.isoformat(): n for d, n in (point_counts or {}).items()}
            if point_counts
            else {}
        )
        normal_font = QFont()

        # ── All dates master toggle ──
        all_action = QAction(f"All dates ({len(dates)})", self._menu)
        all_action.setCheckable(True)
        all_action.setChecked(True)
        all_action.triggered.connect(self._on_all_toggled)
        self._menu.addAction(all_action)
        self._all_action = all_action

        self._menu.addSeparator()

        # ── Hide stationary toggle ──
        hide_st = QAction("Hide stationary days", self._menu)
        hide_st.setCheckable(True)
        hide_st.setChecked(True)
        hide_st.triggered.connect(self._on_hide_stationary_toggled)
        self._menu.addAction(hide_st)
        self._hide_st_action = hide_st

        self._menu.addSeparator()

        # ── one row per date ──
        for d in dates:
            iso = d.isoformat()
            is_stationary = iso in self._stationary_set
            pt_count = counts.get(iso, 0)
            label = f"{iso}  \u00B7 {pt_count:,} pts" if pt_count else iso

            action = QAction(label, self._menu)
            action.setCheckable(True)
            action.setData(iso)
            action.setChecked(not is_stationary)  # moving dates on by default

            if is_stationary:
                italic_font = QFont()
                italic_font.setItalic(True)
                action.setFont(italic_font)
                # hidden while "Hide stationary" is ON
                action.setVisible(not hide_st.isChecked())
            else:
                action.setFont(normal_font)

            action.triggered.connect(self._on_date_toggled)
            self._menu.addAction(action)
            self._date_actions.append(action)

        self._sync_all_action()
        self._update_summary()

    def selected_dates(self) -> list[str]:
        """ISO date strings of all currently checked (and visible) dates."""
        return [
            a.data()
            for a in self._date_actions
            if a.isVisible() and a.isChecked()
        ]

    def stationary_hidden(self) -> bool:
        """Whether the ``Hide stationary days`` toggle is checked (ON)."""
        return bool(self._hide_st_action and self._hide_st_action.isChecked())

    def clear(self) -> None:
        """Reset the widget to empty state."""
        self._menu.clear()
        self._date_actions.clear()
        self._stationary_set.clear()
        self._all_action = None
        self._hide_st_action = None
        self._summary.setText("")

    # ── internal slots ────────────────────────────────────────────

    def _on_all_toggled(self, checked: bool) -> None:
        for a in self._date_actions:
            if a.isVisible():
                a.setChecked(checked)
        self._sync_all_action()
        self._update_summary()
        self.selection_changed.emit()

    def _on_hide_stationary_toggled(self, checked: bool) -> None:
        # checked == True  → "Hide stationary" is ON  → hide stationary rows
        # checked == False → "Hide stationary" is OFF → show stationary rows
        for a in self._date_actions:
            if a.data() in self._stationary_set:
                a.setVisible(not checked)
        self._sync_all_action()
        self._update_summary()
        self.selection_changed.emit()

    def _on_date_toggled(self) -> None:
        self._sync_all_action()
        self._update_summary()
        self.selection_changed.emit()

    def _sync_all_action(self) -> None:
        """Keep the master toggle in sync with individual rows."""
        if not self._all_action:
            return
        visible = [a for a in self._date_actions if a.isVisible()]
        all_checked = visible and all(a.isChecked() for a in visible)
        self._all_action.setChecked(all_checked)

    def _update_summary(self) -> None:
        visible = [a for a in self._date_actions if a.isVisible()]
        selected = sum(1 for a in visible if a.isChecked())
        self._summary.setText(f"{selected}/{len(visible)} days")
