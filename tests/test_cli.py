from adguard_tray.cli import find_url, parse_locations, parse_status

LOCS = (
    "\x1b[1mISO   COUNTRY              CITY                           PING ESTIMATE\n"
    "\x1b[0mSE    Sweden               Stockholm                      34        \n"
    "FI    Finland              Helsinki                       44        \n"
    "US    United States        New York                       120       \n"
    "JP    Japan                Tokyo                                    \n"
)


def test_parse_locations():
    locs = parse_locations(LOCS)
    assert [l.iso for l in locs] == ["SE", "FI", "US", "JP"]
    assert locs[2].city == "New York" and locs[2].country == "United States"
    assert locs[1].ping == 44 and locs[3].ping is None


def test_status_connected():
    st = parse_status("Connected to \x1b[1mHELSINKI\x1b[0m in \x1b[1mTUN\x1b[0m mode, running on tun0\n")
    assert st.connected and st.location == "HELSINKI" and st.mode == "TUN"


def test_status_other():
    assert parse_status("VPN is disconnected\nYou can connect ...").state == "disconnected"
    assert parse_status("You are not logged in").state == "logged_out"
    assert parse_status("VPN is starting").state == "starting"


def test_find_url():
    t = "You need to authorize in your browser. The following link will be available for 300 seconds: https://auth.adguard.io/x?y=1\n"
    assert find_url(t) == "https://auth.adguard.io/x?y=1"


def test_vpn_process_detection(tmp_path):
    from adguard_tray.cli import find_vpn_process, parse_success, tun_up

    def mk(pid, argv):
        d = tmp_path / "proc" / str(pid)
        d.mkdir(parents=True)
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")

    mk(10, ["sudo", "HOME=/h", "adguardvpn-cli", "connect", "--no-fork", "--location", "FI"])
    mk(11, ["bash"])
    mk(12, ["adguardvpn-cli", "connect", "--no-fork", "--location", "FI"])
    (tmp_path / "proc" / "self").mkdir()
    p = find_vpn_process(tmp_path / "proc")
    assert p.pid == 12 and p.location_arg == "FI"

    net = tmp_path / "net"
    (net / "cnem_vnic").mkdir(parents=True)
    assert not tun_up(net)
    (net / "tun0").mkdir()
    assert tun_up(net)
    assert parse_success("\x1b[1mSuccessfully Connected to HELSINKI\x1b[0m") == "HELSINKI"
