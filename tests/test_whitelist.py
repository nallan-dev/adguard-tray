from adguard_tray import cli, whitelist

TEXT = """\
# comment
anthropic.com          # API
*.claude.ai
www.youtube.com
=challenges.cloudflare.com
=YT3.GoogleUserContent.com
203.0.113.10
198.51.100.0/24
1.2.3.4:443
2001:db8::/32
[2001:db8::1]:8443

anthropic.com          # duplicate
"""


def test_parse_entries():
    entries, errors = whitelist.parse(TEXT)
    assert errors == []
    assert entries == sorted({
        "anthropic.com", "*.anthropic.com",
        "claude.ai", "*.claude.ai",
        "youtube.com", "*.youtube.com",
        "challenges.cloudflare.com",
        "yt3.googleusercontent.com",
        "203.0.113.10", "198.51.100.0/24", "1.2.3.4:443",
        "2001:db8::/32", "[2001:db8::1]:8443",
    })


def test_parse_errors_and_count():
    text = "good.com\nbad domain.com\nfoo\n=\n# only comment\n"
    entries, errors = whitelist.parse(text)
    assert entries == ["*.good.com", "good.com"]
    assert [e.line_no for e in errors] == [2, 3, 4]
    assert whitelist.count_records(text) == 4


def test_templates_have_no_records():
    for lang in whitelist.TEMPLATES:
        tpl = whitelist.template(lang)
        assert whitelist.count_records(tpl) == 0
        assert whitelist.parse(tpl) == ([], [])


def test_load_creates_template(tmp_path):
    path = tmp_path / "sub" / "whitelist.txt"
    text = whitelist.load_text("ru", path)
    assert path.read_text() == text == whitelist.template("ru")
    whitelist.save_text("a.com", path)
    assert whitelist.load_text("ru", path) == "a.com\n"


def test_parse_mode():
    assert cli.parse_mode("Current exclusion mode is \x1b[1mSELECTIVE\x1b[0m") == "selective"
    assert cli.parse_mode("Current exclusion mode is GENERAL") == "general"
    assert cli.parse_mode("You are not logged in") == "unknown"


def test_root_batch(monkeypatch):
    cmds = [["site-exclusions", "clear"], ["site-exclusions", "add", "*.a.com"]]
    monkeypatch.setattr(cli, "sudo_allowed", lambda _c: True)
    batch = cli.root_batch(cmds)
    assert [b[0] for b in batch] == ["sudo", "sudo"]
    assert batch[1][1][-1] == "*.a.com"
    monkeypatch.setattr(cli, "sudo_allowed", lambda _c: False)
    [(prog, argv)] = cli.root_batch(cmds)
    assert prog == "pkexec" and argv[2:4] == ["sh", "-c"]
    assert " && " in argv[4] and "'*.a.com'" in argv[4]  # glob is quoted for sh
