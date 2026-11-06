from __future__ import annotations

import os
import signal
import sys

from PySide6.QtGui import QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import i18n, theme
from .cli import Status
from .config import Config
from .controller import VpnController
from .i18n import tr
from .window import MainWindow, state_text

SERVER_NAME = f"adguard-tray-{os.getuid()}"


def _already_running() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


class TrayApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.cfg = Config.load()
        i18n.set_lang(self.cfg.lang or i18n.detect())
        self.ctrl = VpnController()
        self.win = MainWindow(self.ctrl, self.cfg)
        self._last_state = "unknown"

        self.tray = QSystemTrayIcon(theme.shield_icon("unknown"))
        self.tray.setToolTip("AdGuard VPN Tray")
        menu = QMenu()
        self.act_show = QAction(menu, triggered=self.win.show_and_raise)
        self.act_toggle = QAction(menu, triggered=self._toggle_vpn)
        self.act_quit = QAction(menu, triggered=self.quit)
        menu.addAction(self.act_show)
        menu.addSeparator()
        menu.addAction(self.act_toggle)
        menu.addSeparator()
        menu.addAction(self.act_quit)
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

        self.ctrl.status_changed.connect(self._on_status)
        self.ctrl.busy_changed.connect(lambda _b: self._on_status(self.ctrl.status))
        self.win.language_changed.connect(lambda _l: self._retranslate())
        self._retranslate()

        self.server = QLocalServer()
        QLocalServer.removeServer(SERVER_NAME)
        self.server.listen(SERVER_NAME)
        self.server.newConnection.connect(self._on_ipc)

        self.ctrl.start()
        if "--hidden" not in sys.argv:
            self.win.show_and_raise()

    def _on_ipc(self) -> None:
        conn = self.server.nextPendingConnection()
        if conn:
            conn.disconnected.connect(conn.deleteLater)
        self.win.show_and_raise()

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.win.toggle_visible()

    def _retranslate(self) -> None:
        self.act_show.setText(tr("tray.open"))
        self.act_quit.setText(tr("tray.quit"))
        self._on_status(self.ctrl.status)

    def _on_status(self, st: Status) -> None:
        self.tray.setIcon(theme.shield_icon(st.state))
        self.win.setWindowIcon(theme.shield_icon(st.state))
        where = f": {st.location}" if st.connected and st.location else ""
        self.tray.setToolTip(f"AdGuard VPN Tray · {state_text(st.state)}{where}")
        if st.state == "logged_out":
            self.act_toggle.setText(tr("tray.login"))
        elif st.connected or st.state == "starting" or self.ctrl.own_process:
            self.act_toggle.setText(tr("btn.disconnect"))
        else:
            label = self.cfg.last_location_title or self.cfg.last_location
            self.act_toggle.setText(tr("tray.connect_to", name=label) if label else tr("btn.connect"))
        self.act_toggle.setEnabled(not self.ctrl.busy)

        prev, self._last_state = self._last_state, st.state
        if prev != "unknown" and prev != st.state and not self.win.isVisible():
            if st.connected:
                self.tray.showMessage("AdGuard VPN", f"{state_text('connected')}{where}", self.tray.icon(), 3000)
            elif st.state == "disconnected" and prev == "connected":
                self.tray.showMessage("AdGuard VPN", state_text("disconnected"), self.tray.icon(), 3000)

    def _toggle_vpn(self) -> None:
        st = self.ctrl.status
        if st.state == "logged_out":
            self.win.show_and_raise()
            self.win._on_action()
        elif st.connected or st.state == "starting" or self.ctrl.own_process:
            self.ctrl.disconnect()
        else:
            self.ctrl.connect_to(self.cfg.last_location)

    def quit(self) -> None:
        self.tray.hide()
        self.ctrl.shutdown()
        self.server.close()
        self.app.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("adguard-tray")
    app.setDesktopFileName("adguard-tray")
    app.setQuitOnLastWindowClosed(False)
    if _already_running():
        return 0
    theme.apply_dark(app)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("warning: system tray is not available", file=sys.stderr)
    tray_app = TrayApp(app)
    signal.signal(signal.SIGINT, lambda *_: tray_app.quit())
    signal.signal(signal.SIGTERM, lambda *_: tray_app.quit())
    # let Python handle signals while Qt loop runs
    from PySide6.QtCore import QTimer

    t = QTimer(interval=500, timeout=lambda: None)
    t.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
