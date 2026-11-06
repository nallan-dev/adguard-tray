"""Async orchestration of adguardvpn-cli via QProcess."""

from __future__ import annotations

from collections import deque
from datetime import datetime

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from . import cli
from .cli import Location, Status
from .i18n import tr

POLL_MS = 2000  # /proc + /sys scan, cheap
CLI_STATUS_MS = 30_000  # `adguardvpn-cli status`: login state / fork-mode connections
LOG_LIMIT = 5000


class VpnController(QObject):
    status_changed = Signal(object)  # Status
    locations_loaded = Signal(list)  # list[Location]
    log_line = Signal(str)
    log_cleared = Signal()
    busy_changed = Signal(bool)
    login_url = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.status = Status("unknown")
        self.locations: list[Location] = []
        self.logs: deque[str] = deque(maxlen=LOG_LIMIT)

        self._conn: QProcess | None = None  # our long-living `connect --no-fork`
        self._conn_location = ""
        self._conn_ok = False  # saw "Successfully Connected to"
        self._aux: QProcess | None = None  # disconnect / login
        self._cli_status_proc: QProcess | None = None
        self._cli_status = Status("unknown")
        self._pending_connect: str | None = None
        self._partial = ""
        self._login_buf = ""
        self._external_pid: int | None = None

        self._timer = QTimer(self, interval=POLL_MS, timeout=self.refresh_status)
        self._cli_timer = QTimer(self, interval=CLI_STATUS_MS, timeout=self._query_cli_status)

    # ---------- public API ----------
    def start(self) -> None:
        self._query_cli_status()
        self.refresh_status()
        self.load_locations()
        self._timer.start()
        self._cli_timer.start()

    @property
    def own_process(self) -> bool:
        return self._conn is not None and self._conn.state() != QProcess.NotRunning

    @property
    def busy(self) -> bool:
        return self._aux is not None and self._aux.state() != QProcess.NotRunning

    def connect_to(self, location: str) -> None:
        if self.own_process or cli.find_vpn_process() or self._cli_status.connected:
            self._pending_connect = location
            self.disconnect()
            return
        self._external_pid = None
        self.logs.clear()
        self.log_cleared.emit()
        self._log(f"--- connect {location or '(last used)'} ---")
        args = ["connect", "--no-fork", "-y"]
        if location:
            args += ["-l", location]
        prog, argv = cli.root_cmd(*args)
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(lambda: self._on_output(p))
        p.finished.connect(lambda code, _st: self._on_conn_finished(p, code))
        p.errorOccurred.connect(lambda err: self._log(f"[error] {err.name}: {p.errorString()}"))
        self._conn = p
        self._conn_location = location
        self._conn_ok = False
        self._partial = ""
        p.start(prog, argv)
        self.refresh_status()

    def disconnect(self) -> None:
        if self.busy:
            return
        proc = cli.find_vpn_process()
        if proc is not None:
            self._log(f"--- disconnect (SIGINT → pid {proc.pid}) ---")
            self._run_aux(cli.kill_cmd(proc.pid), self._after_disconnect)
        elif self._cli_status.connected:  # daemon started in fork mode
            self._log("--- disconnect ---")
            self._run_aux(cli.root_cmd("disconnect"), self._after_disconnect)
        else:
            self._log(tr("log.no_process"))
            self._after_disconnect(0)

    def login(self) -> None:
        if self.busy:
            return
        self._log("--- login ---")
        self._login_buf = ""
        self._run_aux(cli.user_cmd("login"), lambda _c: self._query_cli_status(), login=True)

    def load_locations(self) -> None:
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)

        def done(_code: int, _st: object) -> None:
            text = bytes(p.readAll()).decode(errors="replace")
            locs = cli.parse_locations(text)
            if locs:
                self.locations = locs
                self.locations_loaded.emit(locs)
                self.refresh_status(force_emit=True)
            p.deleteLater()

        p.finished.connect(done)
        p.start(*cli.user_cmd("list-locations"))

    def refresh_status(self, force_emit: bool = False) -> None:
        proc = cli.find_vpn_process()
        if proc is not None or self.own_process:
            up = cli.tun_up() or self._conn_ok
            loc = self._conn_location if self.own_process else ""
            loc = loc or (proc.location_arg if proc else "")
            st = Status("connected" if up else "starting", self.pretty_location(loc))
            if proc is not None and not self.own_process and self._external_pid != proc.pid:
                self._external_pid = proc.pid
                self.logs.clear()
                self.log_cleared.emit()
                self._log(tr("log.external", pid=proc.pid, cmd=" ".join(proc.argv)))
                self._log(tr("log.external_hint"))
        else:
            self._external_pid = None
            st = self._cli_status
            if st.connected:
                st = Status("connected", self.pretty_location(st.location), st.mode, st.raw)
        self._set_status(st, force_emit)

    def pretty_location(self, value: str) -> str:
        v = value.strip().lower()
        if not v:
            return ""
        for loc in self.locations:
            if v in (loc.iso.lower(), loc.city.lower(), loc.country.lower()):
                return loc.title
        return value.strip().title()

    def shutdown(self, timeout_ms: int = 8000) -> None:
        """Stop the VPN only if this GUI started it."""
        self._timer.stop()
        self._cli_timer.stop()
        if not self.own_process:
            return
        proc = cli.find_vpn_process()
        if proc is not None:
            p = QProcess()
            p.start(*cli.kill_cmd(proc.pid))
            p.waitForFinished(timeout_ms)
        if self._conn is not None and not self._conn.waitForFinished(timeout_ms):
            self._conn.kill()

    # ---------- internals ----------
    def _query_cli_status(self) -> None:
        if self._cli_status_proc is not None:
            return
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        self._cli_status_proc = p

        def done(_code: int, _st: object) -> None:
            self._cli_status = cli.parse_status(bytes(p.readAll()).decode(errors="replace"))
            self._cli_status_proc = None
            p.deleteLater()
            self.refresh_status()

        p.finished.connect(done)
        p.errorOccurred.connect(lambda _e: setattr(self, "_cli_status_proc", None))
        p.start(*cli.user_cmd("status"))

    def _run_aux(self, cmd: tuple[str, list[str]], on_done, login: bool = False) -> None:
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(lambda: self._on_output(p, login=login))

        def finished(code: int, _st: object) -> None:
            self._flush_partial()
            if code:
                self._log(f"[exit {code}]")
            self._aux = None
            p.deleteLater()
            self.busy_changed.emit(False)
            on_done(code)

        p.finished.connect(finished)
        p.errorOccurred.connect(lambda err: self._log(f"[error] {err.name}: {p.errorString()}"))
        self._aux = p
        self.busy_changed.emit(True)
        p.start(*cmd)

    def _after_disconnect(self, _code: int) -> None:
        self._query_cli_status()
        if self._pending_connect is None:
            self.refresh_status()
            return
        # wait until the old process is really gone, then connect to the new location
        waited = {"ms": 0}

        def check() -> None:
            if self.own_process or cli.find_vpn_process():
                waited["ms"] += 300
                if waited["ms"] < 15_000:
                    QTimer.singleShot(300, check)
                else:
                    self._log(tr("log.reconnect_cancelled"))
                    self._pending_connect = None
                return
            if self._pending_connect is not None:
                loc, self._pending_connect = self._pending_connect, None
                self.connect_to(loc)

        QTimer.singleShot(300, check)

    def _on_output(self, p: QProcess, login: bool = False) -> None:
        chunk = bytes(p.readAllStandardOutput()).decode(errors="replace")
        if login:
            self._login_buf += chunk
            if url := cli.find_url(self._login_buf):
                self._login_buf = ""
                self.login_url.emit(url)
            tail = cli.strip_ansi(chunk).rstrip().lower()
            if tail.endswith("?") or "[y/n]" in tail or "(y/n)" in tail:
                p.write(b"y\n")
        text = self._partial + cli.strip_ansi(chunk)
        *lines, self._partial = text.split("\n")
        for line in lines:
            if line.strip():
                self._log(line.rstrip())
                if p is self._conn and (loc := cli.parse_success(line)):
                    self._conn_ok = True
                    self._conn_location = self._conn_location or loc
                    self.refresh_status()

    def _flush_partial(self) -> None:
        if self._partial.strip():
            self._log(self._partial.rstrip())
        self._partial = ""

    def _on_conn_finished(self, p: QProcess, code: int) -> None:
        self._flush_partial()
        self._log(f"[connect process exited with code {code}]")
        if self._conn is p:
            self._conn = None
            self._conn_ok = False
        p.deleteLater()
        self.refresh_status()

    def _log(self, line: str) -> None:
        stamped = f"{datetime.now():%H:%M:%S}  {line}"
        self.logs.append(stamped)
        self.log_line.emit(stamped)

    def _set_status(self, st: Status, force_emit: bool = False) -> None:
        changed = (st.state, st.location) != (self.status.state, self.status.location)
        self.status = st
        if changed or force_emit:
            self.status_changed.emit(st)
