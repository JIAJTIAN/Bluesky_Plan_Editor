"""Shared geometry, colour, font and style constants for all canvas items.

Import from here instead of defining locally in node.py / loop_frame.py / port.py
so a single edit propagates everywhere.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont

# ── port geometry ─────────────────────────────────────────────────────────────
PORT_R      = 7          # radius of port circle, px
PORT_ROW_H  = 36         # vertical spacing between port rows, px

# ── port colours ──────────────────────────────────────────────────────────────
PORT_COLORS: dict[str, QColor] = {
    "plan":  QColor("#a855f7"),   # purple
    "value": QColor("#f59e0b"),   # amber
}

PLAN_COLOR  = PORT_COLORS["plan"]
VALUE_COLOR = PORT_COLORS["value"]

# ── node geometry ─────────────────────────────────────────────────────────────
HEADER_H    = 28         # node header height, px
NODE_W      = 200        # default node width, px
FIELD_H     = 22         # param field row height, px
NODE_PAD    = 8          # horizontal padding inside nodes, px

# ── node colours ──────────────────────────────────────────────────────────────
NODE_BG         = QColor("#141922")
NODE_HEADER_BG  = QColor("#1e2535")
NODE_BORDER     = QColor("#2a3548")
NODE_MUTED_BG   = QColor("#0f1117")
NODE_SEL_BORDER = QColor("#7dd3fc")
NODE_TITLE_CLR  = QColor("#e2e8f0")
NODE_LABEL_CLR  = QColor("#64748b")

# ── loop-frame geometry ───────────────────────────────────────────────────────
FRAME_HEADER_H  = 32
FRAME_PAD       = 12
FRAME_MIN_W     = 500
FRAME_MIN_H     = 300

# ── loop-frame colours ────────────────────────────────────────────────────────
FRAME_BG        = QColor("#091a09")
FRAME_BORDER    = QColor("#4ade80")
FRAME_HDR_BG    = QColor("#0f3a0f")
FRAME_TITLE_CLR = QColor("#4ade80")
FRAME_LABEL_CLR = QColor("#94a3b8")

# ── fonts ─────────────────────────────────────────────────────────────────────
TITLE_FONT = QFont("Segoe UI", 9)
TITLE_FONT.setBold(True)

LABEL_FONT = QFont("Segoe UI", 8)

# ── shared button style ───────────────────────────────────────────────────────
BTN_STYLE = (
    "QPushButton { background:#1e2535; color:#64748b; border:1px solid #2e3a50;"
    " font-size:11px; font-weight:bold; border-radius:3px; padding:0; }"
    "QPushButton:hover { background:#2e3a50; color:#94a3b8; }"
    "QPushButton:pressed { background:#0f1117; }"
)
