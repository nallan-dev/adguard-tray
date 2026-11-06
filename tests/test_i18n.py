import string

from adguard_tray import i18n


def test_same_keys_and_placeholders():
    ru, en = i18n.STRINGS["ru"], i18n.STRINGS["en"]
    assert ru.keys() == en.keys()
    fields = lambda s: {f for _, f, _, _ in string.Formatter().parse(s) if f}
    for k in ru:
        assert fields(ru[k]) == fields(en[k]), k


def test_detect(monkeypatch):
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        monkeypatch.delenv(var, raising=False)
    assert i18n.detect() == "en"
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    assert i18n.detect() == "ru"
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    assert i18n.detect() == "en"


def test_tr_fallback_and_format():
    i18n.set_lang("xx")
    assert i18n.get_lang() == "en"
    i18n.set_lang("ru")
    assert i18n.tr("loc.selected", name="Riga") == "Локация: Riga"
    assert i18n.tr("no.such.key") == "no.such.key"
    i18n.set_lang("en")
