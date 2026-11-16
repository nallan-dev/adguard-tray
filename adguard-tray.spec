# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build spec: `make build` runs `pyinstaller adguard-tray.spec`.

# Libraries that must come from the user's system, not from the build machine.
# libxkbcommon: Qt's xcb plugin also loads the system libxkbcommon-x11, which is
# tied to the system libxkbcommon of the same version. Bundling the build host's
# (older) libxkbcommon next to a newer system libxkbcommon-x11 crashes the app
# with a segfault on keyboard input (e.g. arrow keys in a text field).
SYSTEM_LIBS = ("libxkbcommon",)

a = Analysis(
    ["run.py"],
    excludes=["tkinter"],
)
a.binaries = [b for b in a.binaries if not b[0].startswith(SYSTEM_LIBS)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="adguard-tray",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
)
