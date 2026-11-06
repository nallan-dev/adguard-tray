from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .cli import Location, Status
from .config import Config
from .controller import VpnController

LOC_ROLE = Qt.UserRole + 1
SEARCH_ROLE = Qt.UserRole + 2

STATE_TEXT = {
    "connected": "Подключено",
    "starting": "Подключение…",
    "disconnected": "Отключено",
    "logged_out": "Требуется вход",
    "unknown": "Статус неизвестен",
}

BASE_WIDTH = 440
LOG_WIDTH = 760


class MainWindow(QWidget):
    def __init__(self, ctrl: VpnController, cfg: Config) -> None:
        super().__init__()
        self.ctrl, self.cfg = ctrl, cfg
        self.setWindowTitle("AdGuard VPN Tray")
        self.setWindowIcon(theme.shield_icon("disconnected"))
        self.resize(BASE_WIDTH, 10)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # --- status card ---
        card = QFrame(objectName="card")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(12)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(44, 44)
        cl.addWidget(self.icon_lbl)
        txt = QVBoxLayout()
        txt.setSpacing(2)
        self.state_lbl = QLabel()
        self.state_lbl.setStyleSheet("font-size: 13pt; font-weight: 600;")
        self.loc_lbl = QLabel(objectName="muted")
        txt.addWidget(self.state_lbl)
        txt.addWidget(self.loc_lbl)
        cl.addLayout(txt, 1)
        self.action_btn = QPushButton()
        self.action_btn.setMinimumWidth(120)
        self.action_btn.clicked.connect(self._on_action)
        cl.addWidget(self.action_btn)
        root.addWidget(card)

        # --- locations section ---
        self.loc_toggle = QToolButton(checkable=True)
        self.loc_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.loc_toggle.toggled.connect(self._toggle_locations)
        root.addWidget(self.loc_toggle)

        self.loc_box = QWidget()
        lb = QVBoxLayout(self.loc_box)
        lb.setContentsMargins(0, 0, 0, 0)
        lb.setSpacing(6)
        self.search = QLineEdit(placeholderText="Поиск: город, страна или ISO…")
        self.search.setClearButtonEnabled(True)
        lb.addWidget(self.search)
        self.model = QStandardItemModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterRole(SEARCH_ROLE)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.search.returnPressed.connect(self._connect_selected_or_first)
        self.list = QListView()
        self.list.setModel(self.proxy)
        self.list.setEditTriggers(QListView.NoEditTriggers)
        self.list.setMinimumHeight(260)
        self.list.setUniformItemSizes(True)
        self.list.doubleClicked.connect(self._connect_index)
        self.list.activated.connect(self._connect_index)
        self.list.clicked.connect(self._select_index)
        lb.addWidget(self.list)
        hint = QLabel("Клик: выбрать · двойной клик / Enter: подключиться", objectName="muted")
        hint.setStyleSheet("font-size: 8.5pt;")
        lb.addWidget(hint)
        self.loc_box.hide()
        root.addWidget(self.loc_box, 1)

        # --- logs section ---
        self.log_toggle = QToolButton(checkable=True)
        self.log_toggle.toggled.connect(self._toggle_logs)
        root.addWidget(self.log_toggle)
        self.log_view = QPlainTextEdit(objectName="log", readOnly=True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_view.setMinimumHeight(280)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_view.hide()
        root.addWidget(self.log_view, 2)

        # signals
        ctrl.status_changed.connect(self._render_status)
        ctrl.busy_changed.connect(lambda _b: self._render_status(ctrl.status))
        ctrl.locations_loaded.connect(self._fill_locations)
        ctrl.log_line.connect(self._append_log)
        ctrl.log_cleared.connect(self.log_view.clear)
        ctrl.login_url.connect(self._open_login_url)

        self._update_toggle_texts()
        self._render_status(ctrl.status)
        if ctrl.locations:
            self._fill_locations(ctrl.locations)

    # ---------- rendering ----------
    def _render_status(self, st: Status) -> None:
        self.icon_lbl.setPixmap(theme.shield_icon(st.state).pixmap(44, 44))
        self.state_lbl.setText(STATE_TEXT.get(st.state, st.state))
        self.state_lbl.setStyleSheet(
            f"font-size: 13pt; font-weight: 600; color: {theme.STATE_COLORS.get(st.state, theme.TEXT)};"
        )
        if st.connected:
            parts = [st.location or "локация неизвестна"]
            if self.ctrl.status.connected and not self.ctrl.own_process:
                parts.append("запущен вне GUI")
            self.loc_lbl.setText(" · ".join(parts))
        else:
            last = self.cfg.last_location_title or self.cfg.last_location
            self.loc_lbl.setText(f"Локация: {last}" if last else "Локация не выбрана: последняя из CLI")

        btn = self.action_btn
        if st.state == "logged_out":
            btn.setText("Войти")
            btn.setObjectName("primary")
        elif st.connected or st.state == "starting" or self.ctrl.own_process:
            btn.setText("Отключить")
            btn.setObjectName("danger")
        else:
            btn.setText("Подключить")
            btn.setObjectName("primary")
        btn.setEnabled(not self.ctrl.busy)
        btn.style().unpolish(btn)
        btn.style().polish(btn)

        can_log = st.connected or st.state == "starting" or self.ctrl.own_process or self.ctrl.busy
        self.log_toggle.setVisible(can_log or self.log_toggle.isChecked())
        if can_log and self.cfg.logs_visible and not self.log_toggle.isChecked():
            self.log_toggle.setChecked(True)

    def _fill_locations(self, locs: list[Location]) -> None:
        self.model.clear()
        for loc in locs:
            ping = f"{loc.ping} ms" if loc.ping is not None else ""
            it = QStandardItem(f"{loc.iso}   {loc.city}, {loc.country}    {ping}")
            it.setData(loc, LOC_ROLE)
            it.setData(loc.search_text, SEARCH_ROLE)
            it.setToolTip(loc.title)
            self.model.appendRow(it)
        self._update_toggle_texts()

    def _append_log(self, line: str) -> None:
        sb = self.log_view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        self.log_view.appendPlainText(line)
        if at_bottom:
            sb.setValue(sb.maximum())

    def _update_toggle_texts(self) -> None:
        n = self.model.rowCount()
        arrow = "▾" if self.loc_toggle.isChecked() else "▸"
        self.loc_toggle.setText(f"{arrow}  Локации ({n})" if n else f"{arrow}  Локации")
        self.log_toggle.setText("▾  Скрыть логи" if self.log_toggle.isChecked() else "▸  Показать логи")

    # ---------- actions ----------
    def _on_action(self) -> None:
        st = self.ctrl.status
        if st.state == "logged_out":
            self.ctrl.login()
            self.log_toggle.setVisible(True)
            self.log_toggle.setChecked(True)
        elif st.connected or st.state == "starting" or self.ctrl.own_process:
            self.ctrl.disconnect()
        else:
            self.ctrl.connect_to(self.cfg.last_location)

    def _select_index(self, idx) -> None:
        loc: Location = idx.data(LOC_ROLE)
        if loc:
            self.cfg.last_location = loc.city
            self.cfg.last_location_title = loc.title
            self.cfg.save()
            self._render_status(self.ctrl.status)

    def _connect_index(self, idx) -> None:
        self._select_index(idx)
        self.ctrl.connect_to(self.cfg.last_location)

    def _connect_selected_or_first(self) -> None:
        idx = self.list.currentIndex()
        if not idx.isValid() and self.proxy.rowCount():
            idx = self.proxy.index(0, 0)
        if idx.isValid():
            self._connect_index(idx)

    def _open_login_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    # ---------- layout toggles ----------
    def _toggle_locations(self, on: bool) -> None:
        self.loc_box.setVisible(on)
        if on:
            if not self.model.rowCount():
                self.ctrl.load_locations()
            self.search.setFocus()
        self._update_toggle_texts()
        self._relayout()

    def _toggle_logs(self, on: bool) -> None:
        self.log_view.setVisible(on)
        self.cfg.logs_visible = on
        self.cfg.save()
        if on:
            self.log_view.setPlainText("\n".join(self.ctrl.logs))
            self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
        self._update_toggle_texts()
        self._relayout()

    def _relayout(self) -> None:
        def apply() -> None:
            width = LOG_WIDTH if self.log_view.isVisible() else BASE_WIDTH
            self.setMinimumSize(0, 0)
            self.layout().activate()
            self.resize(width, self.sizeHint().height())

        QTimer.singleShot(0, apply)

    # ---------- window behaviour ----------
    def toggle_visible(self) -> None:
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.show_and_raise()

    def show_and_raise(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()
        self.ctrl.refresh_status()

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide()
