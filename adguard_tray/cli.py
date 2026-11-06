"""Thin wrapper over adguardvpn-cli: parsing and command lines."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

CLI = shutil.which("adguardvpn-cli") or "/usr/local/bin/adguardvpn-cli"
DATA_DIR = Path.home() / ".local/share/adguardvpn-cli"
APP_LOG = DATA_DIR / "app.log"

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][A-Za-z0-9]|\r")
_URL = re.compile(r"https?://\S+")
_CONNECTED = re.compile(r"Connected to (.+?) in (\S+) mode", re.IGNORECASE)


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


@dataclass(frozen=True)
class Location:
    iso: str
    country: str
    city: str
    ping: int | None

    @property
    def title(self) -> str:
        return f"{self.city}, {self.country} ({self.iso})"

    @property
    def search_text(self) -> str:
        return f"{self.iso} {self.country} {self.city}".lower()


@dataclass(frozen=True)
class Status:
    state: str  # connected | disconnected | starting | logged_out | unknown
    location: str = ""
    mode: str = ""
    raw: str = ""

    @property
    def connected(self) -> bool:
        return self.state == "connected"


def parse_locations(text: str) -> list[Location]:
    result: list[Location] = []
    for line in strip_ansi(text).splitlines():
        line = line.strip()
        if not line or line.upper().startswith("ISO"):
            continue
        parts = re.split(r"\s{2,}", line)
        if len(parts) < 3 or not re.fullmatch(r"[A-Z]{2}", parts[0]):
            continue
        ping = None
        if len(parts) >= 4 and parts[3].strip().isdigit():
            ping = int(parts[3])
        result.append(Location(parts[0], parts[1], parts[2], ping))
    return result


def parse_status(text: str) -> Status:
    clean = strip_ansi(text).strip()
    low = clean.lower()
    if m := _CONNECTED.search(clean):
        return Status("connected", m.group(1).strip(), m.group(2), clean)
    if "not logged in" in low or "please log in" in low:
        return Status("logged_out", raw=clean)
    if "is starting" in low or "connecting" in low:
        return Status("starting", raw=clean)
    if "disconnected" in low:
        return Status("disconnected", raw=clean)
    return Status("unknown", raw=clean)


def find_url(text: str) -> str | None:
    m = _URL.search(strip_ansi(text))
    return m.group(0).rstrip(".,)") if m else None


KILL = next((k for k in ("/usr/bin/kill", "/bin/kill") if Path(k).exists()), "kill")

_sudo_cache: dict[str, bool] = {}


def sudo_allowed(cmd: str) -> bool:
    """True if `sudo -n <cmd>` is permitted without a password."""
    if cmd not in _sudo_cache:
        try:
            r = subprocess.run(
                ["sudo", "-n", "-l", cmd], capture_output=True, timeout=5, check=False
            )
            _sudo_cache[cmd] = r.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _sudo_cache[cmd] = False
    return _sudo_cache[cmd]


def root_cmd(*args: str) -> tuple[str, list[str]]:
    """Program + argv to run adguardvpn-cli as root, preserving user's HOME.

    Uses passwordless sudo when configured, otherwise pkexec (polkit password dialog).
    """
    home = f"HOME={os.environ.get('HOME', str(Path.home()))}"
    if sudo_allowed(CLI):
        return "sudo", ["-n", home, CLI, *args]
    return "pkexec", ["env", home, CLI, *args]


def user_cmd(*args: str) -> tuple[str, list[str]]:
    return CLI, list(args)


def kill_cmd(pid: int, sig: str = "INT") -> tuple[str, list[str]]:
    """Stop a root-owned `connect --no-fork` process the same way Ctrl+C does."""
    if sudo_allowed(KILL):
        return "sudo", ["-n", KILL, f"-{sig}", str(pid)]
    return "pkexec", [KILL, f"-{sig}", str(pid)]



# --- process / interface detection -------------------------------------------
# In `--no-fork` mode the CLI writes no pid file, so `status` always says
# "disconnected" and `disconnect` fails with "Process is not running".
# Hence we detect the running VPN ourselves.

_SUCCESS = re.compile(r"Successfully Connected to (.+)", re.IGNORECASE)


@dataclass(frozen=True)
class VpnProcess:
    pid: int
    argv: tuple[str, ...]

    @property
    def location_arg(self) -> str:
        a = self.argv
        for i, x in enumerate(a):
            if x in ("-l", "--location") and i + 1 < len(a):
                return a[i + 1]
            if x.startswith("--location="):
                return x.split("=", 1)[1]
        return ""


def is_vpn_argv(argv: list[str] | tuple[str, ...]) -> bool:
    return bool(argv) and os.path.basename(argv[0]) == "adguardvpn-cli" and "connect" in argv[1:]


def find_vpn_process(proc_root: Path = Path("/proc")) -> VpnProcess | None:
    for d in proc_root.iterdir():
        if not d.name.isdigit():
            continue
        try:
            raw = (d / "cmdline").read_bytes()
        except OSError:
            continue
        argv = [x.decode(errors="replace") for x in raw.split(b"\0") if x]
        if is_vpn_argv(argv):
            return VpnProcess(int(d.name), tuple(argv))
    return None


def tun_up(net_root: Path = Path("/sys/class/net")) -> bool:
    return any(net_root.glob("tun*"))


def parse_success(line: str) -> str | None:
    m = _SUCCESS.search(strip_ansi(line))
    return m.group(1).strip() if m else None
