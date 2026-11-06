# Third-party components

The prebuilt `adguard-tray` binary (PyInstaller one-file bundle) contains:

| Component | License | Source |
|---|---|---|
| Qt 6 / PySide6 / Shiboken6 (`PySide6-Essentials`) | LGPL-3.0-only (or GPL-2.0/3.0) | https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| CPython | PSF License | https://github.com/python/cpython |
| PyInstaller bootloader | GPL-2.0 with bootloader exception | https://github.com/pyinstaller/pyinstaller |

## LGPL notice (Qt / PySide6)

This application dynamically uses the Qt and PySide6 libraries under the GNU Lesser
General Public License v3. The full source code of this application and the build
script (`make build`) are published in this repository. You can rebuild the binary
against your own modified version of PySide6/Qt by installing it into the project
environment (`uv pip install <your PySide6 build>`) and running `make build`, or run the
application directly from source with your own Qt libraries (`make run`).

License texts: https://www.gnu.org/licenses/lgpl-3.0.html, https://www.gnu.org/licenses/gpl-3.0.html

## Not included

`adguardvpn-cli` is **not** bundled or redistributed. It is proprietary software by
AdGuard Software Ltd., installed separately by the user, and governed by its own EULA.
This project only invokes it as an external program.
