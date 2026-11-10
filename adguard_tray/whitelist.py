"""Whitelist for AdGuard's *selective* exclusion mode.

File format (one record per line, `#` starts a comment):
    example.com        domain and all its subdomains (→ example.com + *.example.com)
    =host.example.com  only this host, no subdomains
    203.0.113.10       IP address (IPv4/IPv6, optional port as AdGuard allows)
    203.0.113.0/24     CIDR range
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG_PATH

WHITELIST_PATH = CONFIG_PATH.parent / "whitelist.txt"

_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")

TEMPLATES = {
    "ru": """\
# Белый список ВЫБОРОЧНОГО режима (Selective): через VPN идут ТОЛЬКО эти адреса,
# весь остальной трафик идёт напрямую. В ОБЩЕМ режиме (General) список не используется.
#
# По одной записи на строку, всё после # — комментарий:
#   example.com          домен и все его поддомены (www., api., cdn., …)
#   =api.example.com     только этот хост, без поддоменов
#   203.0.113.10         IP-адрес
#   203.0.113.0/24       подсеть
#
# Сайту обычно нужны и его служебные домены (CDN, API, авторизация). Например, YouTube:
#   youtube.com
#   ytimg.com
#   googlevideo.com
#   =youtubei.googleapis.com
#
# Широкие общие домены (googleapis.com, cloudflare.com, amazonaws.com) лучше не добавлять
# целиком, только конкретный хост через «=».
# После сохранения переподключитесь, чтобы AdGuard применил список.

""",
    "en": """\
# Whitelist for SELECTIVE mode: ONLY these addresses go through the VPN,
# all other traffic goes directly. In GENERAL mode this list is not used.
#
# One record per line, everything after # is a comment:
#   example.com          the domain and all its subdomains (www., api., cdn., …)
#   =api.example.com     only this host, no subdomains
#   203.0.113.10         an IP address
#   203.0.113.0/24       a subnet
#
# A site usually also needs its service domains (CDN, API, auth). For example, YouTube:
#   youtube.com
#   ytimg.com
#   googlevideo.com
#   =youtubei.googleapis.com
#
# Avoid adding broad shared domains (googleapis.com, cloudflare.com, amazonaws.com)
# as a whole; add a specific host with "=" instead.
# After saving, reconnect so that AdGuard applies the list.

""",
}


@dataclass(frozen=True)
class ParseError:
    line_no: int
    text: str


def template(lang: str) -> str:
    return TEMPLATES.get(lang, TEMPLATES["en"])


def load_text(lang: str, path: Path = WHITELIST_PATH) -> str:
    """Read the whitelist file, creating it from the template if it does not exist."""
    try:
        return path.read_text()
    except FileNotFoundError:
        text = template(lang)
        save_text(text, path)
        return text


def save_text(text: str, path: Path = WHITELIST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text)


def _is_ip(value: str) -> bool:
    v = value
    if v.startswith("[") and "]" in v:  # [IPv6] or [IPv6]:port
        v = v[1 : v.index("]")]
    elif v.count(":") == 1:  # IPv4:port
        host, _, port = v.partition(":")
        if not port.isdigit():
            return False
        v = host
    try:
        ipaddress.ip_network(v, strict=False)
        return True
    except ValueError:
        return False


def _records(text: str):
    for no, raw in enumerate(text.splitlines(), 1):
        value = raw.split("#", 1)[0].strip()
        if value:
            yield no, raw, value


def count_records(text: str) -> int:
    return sum(1 for _ in _records(text))


def parse(text: str) -> tuple[list[str], list[ParseError]]:
    """Turn the file into AdGuard exclusion entries. Returns (entries, errors)."""
    entries: set[str] = set()
    errors: list[ParseError] = []
    for no, raw, value in _records(text):
        if any(ch.isspace() for ch in value):
            errors.append(ParseError(no, raw.strip()))
            continue
        exact = value.startswith("=")
        v = value[1:] if exact else value
        if _is_ip(v):
            entries.add(v)
            continue
        v = v.lower().rstrip(".")
        if not exact:
            v = v.removeprefix("*.").removeprefix("www.")
        if not _DOMAIN.match(v):
            errors.append(ParseError(no, raw.strip()))
            continue
        entries.add(v)
        if not exact:
            entries.add(f"*.{v}")
    return sorted(entries), errors
