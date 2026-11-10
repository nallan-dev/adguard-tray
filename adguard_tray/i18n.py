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
        "loc.refresh": "Обновить список локаций и пинг",
        "logs.show": "Показать логи",
        "logs.hide": "Скрыть логи",
        "lang.tooltip": "Язык интерфейса",
        "mode.general": "Общий",
        "mode.selective": "Выборочный",
        "mode.unknown": "Режим ?",
        "mode.menu.general": "Общий: весь трафик через VPN",
        "mode.menu.selective": "Выборочный: через VPN только белый список",
        "mode.tooltip": "Режим AdGuard: что пускать через VPN",
        "wl.toggle": "Белый список",
        "wl.save": "Сохранить",
        "wl.revert": "Отменить",
        "wl.saved": "Сохранено, в AdGuard загружено записей: {n}",
        "wl.save_failed": "Не удалось загрузить список в AdGuard, подробности в логах",
        "wl.errors": "Не похоже на домен или IP, строки: {lines}",
        "wl.modified": "Есть несохранённые изменения",
        "wl.busy": "Выполняется другая команда, попробуйте через пару секунд",
        "wl.empty_title": "Белый список пуст",
        "wl.empty_text": "В выборочном режиме через VPN не пойдёт ничего, пока вы не добавите адреса. Включить всё равно?",
        "notice.reconnect": "Настройки изменены. Переподключитесь, чтобы AdGuard их применил.",
        "btn.reconnect": "Переподключить",
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
        "loc.refresh": "Refresh locations and ping",
        "logs.show": "Show logs",
        "logs.hide": "Hide logs",
        "lang.tooltip": "Interface language",
        "mode.general": "General",
        "mode.selective": "Selective",
        "mode.unknown": "Mode ?",
        "mode.menu.general": "General: all traffic through the VPN",
        "mode.menu.selective": "Selective: only the whitelist through the VPN",
        "mode.tooltip": "AdGuard mode: what goes through the VPN",
        "wl.toggle": "Whitelist",
        "wl.save": "Save",
        "wl.revert": "Revert",
        "wl.saved": "Saved, {n} entries loaded into AdGuard",
        "wl.save_failed": "Could not load the list into AdGuard, see the logs",
        "wl.errors": "Not a domain or IP, lines: {lines}",
        "wl.modified": "Unsaved changes",
        "wl.busy": "Another command is running, try again in a few seconds",
        "wl.empty_title": "Whitelist is empty",
        "wl.empty_text": "In selective mode nothing will go through the VPN until you add addresses. Enable it anyway?",
        "notice.reconnect": "Settings changed. Reconnect so that AdGuard applies them.",
        "btn.reconnect": "Reconnect",
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
