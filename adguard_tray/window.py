from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QListView,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import i18n, theme, whitelist
from .cli import Location, Status
from .config import Config
from .controller import VpnController
from .i18n import tr

LOC_ROLE = Qt.UserRole + 1
SEARCH_ROLE = Qt.UserRole + 2


def state_text(state: str) -> str:
    return tr(f"state.{state}")

BASE_WIDTH = 440
LOG_WIDTH = 760


class MainWindow(QWidget):
    language_changed = Signal(str)

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
        self.loc_lbl.setWordWrap(True)
        txt.addWidget(self.state_lbl)
        txt.addWidget(self.loc_lbl)
        cl.addLayout(txt, 1)
        self.action_btn = QPushButton()
        self.action_btn.setMinimumWidth(120)
        self.action_btn.clicked.connect(self._on_action)
        cl.addWidget(self.action_btn)
        root.addWidget(card)

        # --- "reconnect to apply" notice ---
        self.notice = QFrame(objectName="notice")
        nl = QHBoxLayout(self.notice)
        nl.setContentsMargins(12, 8, 8, 8)
        nl.setSpacing(10)
        self.notice_lbl = QLabel(wordWrap=True)
        nl.addWidget(self.notice_lbl, 1)
        self.reconnect_btn = QPushButton(objectName="primary")
        self.reconnect_btn.clicked.connect(self.ctrl.reconnect)
        nl.addWidget(self.reconnect_btn)
        self.notice.hide()
        root.addWidget(self.notice)

        # --- locations section ---
        self.loc_toggle = QToolButton(checkable=True)
        self.loc_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.loc_toggle.toggled.connect(self._toggle_locations)
        self.mode_btn = QToolButton(objectName="pill")
        self.mode_btn.setPopupMode(QToolButton.InstantPopup)
        mode_menu = QMenu(self.mode_btn)
        mode_group = QActionGroup(mode_menu)
        self.mode_actions: dict[str, QAction] = {}
        for code in ("general", "selective"):
            act = QAction(mode_menu, checkable=True)
            act.triggered.connect(lambda _c=False, code=code: self._request_mode(code))
            mode_group.addAction(act)
            mode_menu.addAction(act)
            self.mode_actions[code] = act
        self.mode_btn.setMenu(mode_menu)
        self.lang_btn = QToolButton(objectName="pill")
        self.lang_btn.setPopupMode(QToolButton.InstantPopup)
        lang_menu = QMenu(self.lang_btn)
        group = QActionGroup(lang_menu)
        for code, label in i18n.LANGS.items():
            act = QAction(label, lang_menu, checkable=True, checked=code == i18n.get_lang())
            act.triggered.connect(lambda _c=False, code=code: self._set_lang(code))
            group.addAction(act)
            lang_menu.addAction(act)
        self.lang_btn.setMenu(lang_menu)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.loc_toggle)
        row.addStretch(1)
        row.addWidget(self.mode_btn)
        row.addWidget(self.lang_btn)
        root.addLayout(row)

        self.loc_box = QWidget()
        lb = QVBoxLayout(self.loc_box)
        lb.setContentsMargins(0, 0, 0, 0)
        lb.setSpacing(6)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.refresh_btn = QToolButton(objectName="iconbtn", text="↻")
        self.refresh_btn.clicked.connect(self.ctrl.load_locations)
        srow = QHBoxLayout()
        srow.setContentsMargins(0, 0, 0, 0)
        srow.setSpacing(6)
        srow.addWidget(self.search, 1)
        srow.addWidget(self.refresh_btn)
        lb.addLayout(srow)
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
        self.hint = QLabel(objectName="muted")
        self.hint.setStyleSheet("font-size: 8.5pt;")
        lb.addWidget(self.hint)
        self.loc_box.hide()
        root.addWidget(self.loc_box, 1)

        # --- whitelist section (selective mode) ---
        self.wl_toggle = QToolButton(checkable=True)
        self.wl_toggle.toggled.connect(self._toggle_whitelist)
        root.addWidget(self.wl_toggle)
        self.wl_box = QWidget()
        wb = QVBoxLayout(self.wl_box)
        wb.setContentsMargins(0, 0, 0, 0)
        wb.setSpacing(6)
        self.wl_edit = QPlainTextEdit(objectName="log")
        self.wl_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.wl_edit.setMinimumHeight(260)
        self.wl_edit.modificationChanged.connect(self._on_wl_modified)
        wb.addWidget(self.wl_edit)
        brow = QHBoxLayout()
        brow.setSpacing(8)
        self.wl_status = QLabel(wordWrap=True)
        brow.addWidget(self.wl_status, 1)
        self.wl_revert_btn = QPushButton()
        self.wl_revert_btn.clicked.connect(self._wl_reload)
        brow.addWidget(self.wl_revert_btn)
        self.wl_save_btn = QPushButton(objectName="primary")
        self.wl_save_btn.clicked.connect(self._wl_save)
        brow.addWidget(self.wl_save_btn)
        wb.addLayout(brow)
        self.wl_box.hide()
        root.addWidget(self.wl_box, 2)
        self._wl_loaded = False
        self._wl_msg = ("", "muted")
        try:
            self._wl_count = whitelist.count_records(whitelist.WHITELIST_PATH.read_text())
        except OSError:
            self._wl_count = 0

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
        ctrl.busy_changed.connect(lambda _b: self._render_mode())
        ctrl.mode_changed.connect(lambda _m: self._render_mode())
        ctrl.pending_apply_changed.connect(lambda _p: self._render_notice())
        ctrl.locations_loaded.connect(self._fill_locations)
        ctrl.locations_loading.connect(lambda busy: self.refresh_btn.setEnabled(not busy))
        ctrl.log_line.connect(self._append_log)
        ctrl.log_cleared.connect(self.log_view.clear)
        ctrl.login_url.connect(self._open_login_url)

        self.retranslate()
        if ctrl.locations:
            self._fill_locations(ctrl.locations)

    # ---------- language ----------
    def retranslate(self) -> None:
        self.search.setPlaceholderText(tr("search.placeholder"))
        self.hint.setText(tr("list.hint"))
        self.refresh_btn.setToolTip(tr("loc.refresh"))
        self.lang_btn.setText(f"{i18n.LANGS[i18n.get_lang()]} ▾")
        self.lang_btn.setToolTip(tr("lang.tooltip"))
        self.wl_revert_btn.setText(tr("wl.revert"))
        self.wl_save_btn.setText(tr("wl.save"))
        self._update_toggle_texts()
        self._render_status(self.ctrl.status)
        self._render_mode()
        self._render_notice()
        self._update_wl_status()

    # ---------- exclusion mode ----------
    def _render_mode(self) -> None:
        mode = self.ctrl.mode
        self.mode_btn.setText(f"{tr(f'mode.{mode}')} ▾")
        self.mode_btn.setToolTip(tr("mode.tooltip"))
        for code, act in self.mode_actions.items():
            act.setText(tr(f"mode.menu.{code}"))
            act.setChecked(code == mode)
        self.mode_btn.setEnabled(not self.ctrl.busy)
        self.wl_toggle.setVisible(mode == "selective" or self.wl_toggle.isChecked())

    def _request_mode(self, mode: str) -> None:
        if mode == self.ctrl.mode:
            self._render_mode()
            return
        entries = None
        if mode == "selective":
            # the saved file is what gets applied; unsaved edits stay in the editor
            entries = self._parse_wl(whitelist.load_text(i18n.get_lang()))
            if entries is None:
                self._render_mode()
                return
            if not entries:
                answer = QMessageBox.question(self, tr("wl.empty_title"), tr("wl.empty_text"))
                if answer != QMessageBox.Yes:
                    self._render_mode()
                    return
        if not self.ctrl.set_mode(mode, entries):
            self._render_mode()

    def _render_notice(self) -> None:
        self.notice_lbl.setText(tr("notice.reconnect"))
        self.reconnect_btn.setText(tr("btn.reconnect"))
        self.reconnect_btn.setEnabled(not self.ctrl.busy)
        if self.notice.isVisible() != self.ctrl.pending_apply:
            self.notice.setVisible(self.ctrl.pending_apply)
            self._relayout()

    # ---------- whitelist ----------
    def _toggle_whitelist(self, on: bool) -> None:
        if on and not self._wl_loaded:
            self._wl_reload()
        self.wl_box.setVisible(on)
        if not on:
            self._render_mode()
        self._update_toggle_texts()
        self._relayout()

    def _show_whitelist(self) -> None:
        self.wl_toggle.setVisible(True)
        self.wl_toggle.setChecked(True)

    def _wl_reload(self) -> None:
        text = whitelist.load_text(i18n.get_lang())
        self.wl_edit.setPlainText(text)
        self.wl_edit.document().setModified(False)
        self._wl_loaded = True
        self._wl_count = whitelist.count_records(text)
        self._set_wl_msg("")
        self._update_toggle_texts()

    def _parse_wl(self, text: str) -> list[str] | None:
        entries, errors = whitelist.parse(text)
        if errors:
            lines = ", ".join(str(e.line_no) for e in errors[:8]) + ("…" if len(errors) > 8 else "")
            self._show_whitelist()
            self._set_wl_msg(tr("wl.errors", lines=lines), "error")
            return None
        return entries

    def _wl_save(self) -> None:
        text = self.wl_edit.toPlainText()
        entries = self._parse_wl(text)
        if entries is None:
            return
        whitelist.save_text(text)
        self.wl_edit.document().setModified(False)
        self._wl_count = whitelist.count_records(text)
        self._update_toggle_texts()

        def done(ok: bool) -> None:
            if ok:
                self._set_wl_msg(tr("wl.saved", n=len(entries)), "ok")
            else:
                self._set_wl_msg(tr("wl.save_failed"), "error")

        if not self.ctrl.apply_whitelist(entries, done):
            self._set_wl_msg(tr("wl.busy"), "error")

    def _on_wl_modified(self, modified: bool) -> None:
        if modified:
            self._wl_msg = ("", "muted")
        self._update_wl_status()

    def _set_wl_msg(self, text: str, kind: str = "muted") -> None:
        self._wl_msg = (text, kind)
        self._update_wl_status()

    def _update_wl_status(self) -> None:
        text, kind = self._wl_msg
        if not text and self.wl_edit.document().isModified():
            text, kind = tr("wl.modified"), "warn"
        color = {"ok": theme.ACCENT, "error": theme.DANGER, "warn": theme.WARN}.get(kind, theme.MUTED)
        self.wl_status.setStyleSheet(f"font-size: 8.5pt; color: {color};")
        self.wl_status.setText(text)

    def _set_lang(self, code: str) -> None:
        if code == i18n.get_lang():
            return
        i18n.set_lang(code)
        self.cfg.lang = code
        self.cfg.save()
        self.retranslate()
        self.language_changed.emit(code)

    # ---------- rendering ----------
    def _render_status(self, st: Status) -> None:
        self.icon_lbl.setPixmap(theme.shield_icon(st.state).pixmap(44, 44))
        self.state_lbl.setText(state_text(st.state))
        self.state_lbl.setStyleSheet(
            f"font-size: 13pt; font-weight: 600; color: {theme.STATE_COLORS.get(st.state, theme.TEXT)};"
        )
        if st.connected:
            parts = [st.location or tr("loc.unknown")]
            if self.ctrl.status.connected and not self.ctrl.own_process:
                parts.append(tr("loc.external"))
            self.loc_lbl.setText(" · ".join(parts))
        else:
            last = self.cfg.last_location_title or self.cfg.last_location
            self.loc_lbl.setText(tr("loc.selected", name=last) if last else tr("loc.none"))

        btn = self.action_btn
        if st.state == "logged_out":
            btn.setText(tr("btn.login"))
            btn.setObjectName("primary")
        elif st.connected or st.state == "starting" or self.ctrl.own_process:
            btn.setText(tr("btn.disconnect"))
            btn.setObjectName("danger")
        else:
            btn.setText(tr("btn.connect"))
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
        title = tr("toggle.locations")
        self.loc_toggle.setText(f"{arrow}  {title} ({n})" if n else f"{arrow}  {title}")
        wl_arrow = "▾" if self.wl_toggle.isChecked() else "▸"
        self.wl_toggle.setText(f"{wl_arrow}  {tr('wl.toggle')} ({self._wl_count})")
        on = self.log_toggle.isChecked()
        self.log_toggle.setText(f"▾  {tr('logs.hide')}" if on else f"▸  {tr('logs.show')}")

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
            wide = self.log_view.isVisible() or self.wl_box.isVisible()
            width = LOG_WIDTH if wide else BASE_WIDTH
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
