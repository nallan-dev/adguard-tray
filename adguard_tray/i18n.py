"""Tiny dictionary-based localisation (ru / en)."""

from __future__ import annotations

import os

LANGS = {"ru": "RU", "en": "EN"}
DEFAULT = "en"

STRINGS: dict[str, dict[str, str]] = {
    "ru": {
        "state.connected": "Подключено",
        "state.starting": "Подключение…",
        "state.disconnected": "Отключено",
        "state.logged_out": "Требуется вход",
        "state.unknown": "Статус неизвестен",
        "loc.unknown": "локация неизвестна",
        "loc.external": "запущен вне GUI",
        "loc.selected": "Локация: {name}",
        "loc.none": "Локация не выбрана: последняя из CLI",
        "btn.login": "Войти",
        "btn.connect": "Подключить",
        "btn.disconnect": "Отключить",
        "search.placeholder": "Поиск: город, страна или ISO…",
        "list.hint": "Клик: выбрать · двойной клик / Enter: подключиться",
        "toggle.locations": "Локации",
        "logs.show": "Показать логи",
        "logs.hide": "Скрыть логи",
        "lang.tooltip": "Язык интерфейса",
        "tray.open": "Открыть окно",
        "tray.login": "Войти…",
        "tray.connect_to": "Подключить ({name})",
        "tray.quit": "Выход",
        "log.no_process": "Нет запущенного VPN-процесса",
        "log.external": "VPN запущен вне GUI: pid {pid}: {cmd}",
        "log.external_hint": "Его вывод идёт в ту консоль, где он запущен; здесь его не перехватить.",
        "log.reconnect_cancelled": "Старый процесс не завершился, переподключение отменено",
    },
    "en": {
        "state.connected": "Connected",
        "state.starting": "Connecting…",
        "state.disconnected": "Disconnected",
        "state.logged_out": "Login required",
        "state.unknown": "Status unknown",
        "loc.unknown": "unknown location",
        "loc.external": "started outside the GUI",
        "loc.selected": "Location: {name}",
        "loc.none": "No location selected: CLI's last used",
        "btn.login": "Log in",
        "btn.connect": "Connect",
        "btn.disconnect": "Disconnect",
        "search.placeholder": "Search: city, country or ISO…",
        "list.hint": "Click: select · double-click / Enter: connect",
        "toggle.locations": "Locations",
        "logs.show": "Show logs",
        "logs.hide": "Hide logs",
        "lang.tooltip": "Interface language",
        "tray.open": "Open window",
        "tray.login": "Log in…",
        "tray.connect_to": "Connect ({name})",
        "tray.quit": "Quit",
        "log.no_process": "No VPN process is running",
        "log.external": "VPN started outside the GUI: pid {pid}: {cmd}",
        "log.external_hint": "Its output goes to the terminal it was started from and cannot be captured here.",
        "log.reconnect_cancelled": "The old process did not exit, reconnect cancelled",
    },
}

_lang = DEFAULT


def detect() -> str:
    """Pick a language from the system locale: ru* → ru, anything else → en."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var, "")
        if value:
            return "ru" if value.lower().startswith("ru") else DEFAULT
    return DEFAULT


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in STRINGS else DEFAULT


def get_lang() -> str:
    return _lang


def tr(key: str, **kwargs: object) -> str:
    text = STRINGS[_lang].get(key) or STRINGS[DEFAULT].get(key, key)
    return text.format(**kwargs) if kwargs else text
