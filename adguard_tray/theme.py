"""Dark theme and programmatically drawn shield icon."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication

BG = "#202124"
SURFACE = "#2a2b2e"
SURFACE_2 = "#333438"
BORDER = "#3c3d41"
TEXT = "#e3e3e3"
MUTED = "#9aa0a6"
ACCENT = "#3fb68b"  # green, connected
WARN = "#e0a83a"  # amber, connecting
DANGER = "#e5534b"
OFF = "#80868b"

STATE_COLORS = {
    "connected": ACCENT,
    "starting": WARN,
    "disconnected": OFF,
    "logged_out": DANGER,
    "unknown": OFF,
}


def apply_dark(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    c = QColor
    p.setColor(QPalette.Window, c(BG))
    p.setColor(QPalette.WindowText, c(TEXT))
    p.setColor(QPalette.Base, c(SURFACE))
    p.setColor(QPalette.AlternateBase, c(SURFACE_2))
    p.setColor(QPalette.ToolTipBase, c(SURFACE_2))
    p.setColor(QPalette.ToolTipText, c(TEXT))
    p.setColor(QPalette.Text, c(TEXT))
    p.setColor(QPalette.Button, c(SURFACE_2))
    p.setColor(QPalette.ButtonText, c(TEXT))
    p.setColor(QPalette.Highlight, c("#2f6f57"))
    p.setColor(QPalette.HighlightedText, c("#ffffff"))
    p.setColor(QPalette.PlaceholderText, c(MUTED))
    p.setColor(QPalette.Link, c(ACCENT))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        p.setColor(QPalette.Disabled, role, c("#6b6e72"))
    app.setPalette(p)
    app.setStyleSheet(
        f"""
        QWidget {{ font-size: 10pt; }}
        QLineEdit, QListView, QPlainTextEdit {{
            background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;
            padding: 4px; selection-background-color: #2f6f57;
        }}
        QLineEdit:focus {{ border-color: {ACCENT}; }}
        QListView::item {{ padding: 5px 4px; border-radius: 4px; }}
        QListView::item:hover {{ background: {SURFACE_2}; }}
        QPushButton {{
            background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 6px;
            padding: 6px 14px;
        }}
        QPushButton:hover {{ background: #3a3b40; }}
        QPushButton:disabled {{ color: #6b6e72; }}
        QPushButton#primary {{ background: #2f6f57; border-color: #3a8a6c; font-weight: 600; }}
        QPushButton#primary:hover {{ background: #378064; }}
        QPushButton#danger {{ background: #5a2a28; border-color: #7a3734; font-weight: 600; }}
        QPushButton#danger:hover {{ background: #6b3230; }}
        QToolButton {{ border: none; color: {MUTED}; padding: 4px 0; font-weight: 600; }}
        QToolButton:hover {{ color: {TEXT}; }}
        QToolButton#lang {{ font-size: 8.5pt; padding: 2px 4px; }}
        QToolButton#lang::menu-indicator {{ image: none; width: 0; }}
        QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
        QLabel#muted {{ color: {MUTED}; }}
        QPlainTextEdit#log {{ font-family: monospace; font-size: 9pt; }}
        QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; padding: 4px; }}
        QMenu::item {{ padding: 5px 18px; border-radius: 4px; }}
        QMenu::item:selected {{ background: {SURFACE_2}; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; }}
        QScrollBar::handle:vertical {{ background: #4a4b50; border-radius: 4px; min-height: 24px; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
        """
    )


def _shield_path(s: float) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(s * 0.5, s * 0.06)
    path.lineTo(s * 0.88, s * 0.2)
    path.cubicTo(s * 0.88, s * 0.58, s * 0.72, s * 0.82, s * 0.5, s * 0.95)
    path.cubicTo(s * 0.28, s * 0.82, s * 0.12, s * 0.58, s * 0.12, s * 0.2)
    path.closeSubpath()
    return path


def shield_icon(state: str) -> QIcon:
    color = QColor(STATE_COLORS.get(state, OFF))
    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPath(_shield_path(size))
        # inner mark: check when connected, dot otherwise
        pen = QPen(QColor(BG), max(1.6, size * 0.09), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        if state == "connected":
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPolyline(
                [QPointF(size * 0.33, size * 0.5), QPointF(size * 0.46, size * 0.63),
                 QPointF(size * 0.68, size * 0.38)]
            )
        else:
            p.setBrush(QColor(BG))
            r = size * 0.11
            p.drawEllipse(QRectF(size * 0.5 - r, size * 0.47 - r, 2 * r, 2 * r))
        p.end()
        icon.addPixmap(pm)
    return icon
