"""Shared category → icon / colour mappings used by palette and search popup.

A single source of truth so both widgets stay consistent.
"""
from __future__ import annotations

# Icon shown next to each category in the node palette and search popup
CATEGORY_ICON: dict[str, str] = {
    "scan":    "⬡",
    "motion":  "→",
    "loop":    "↻",
    "acquire": "◉",
    "run":     "▶",
    "control": "⏸",
    "flow":    "⇄",
    "custom":  "✦",
    "output":  "▣",
    "device":  "⬟",
}

# Accent colour for each category label
CATEGORY_COLOR: dict[str, str] = {
    "scan":    "#7dd3fc",   # sky blue
    "motion":  "#fbbf24",   # amber
    "loop":    "#4ade80",   # green
    "acquire": "#f472b6",   # pink
    "run":     "#86efac",   # light green
    "control": "#fb923c",   # orange
    "flow":    "#f87171",   # red
    "custom":  "#c084fc",   # purple
    "output":  "#94a3b8",   # slate
    "device":  "#34d399",   # emerald green
}

# Fallbacks for unknown categories
DEFAULT_ICON  = "•"
DEFAULT_COLOR = "#94a3b8"


def icon(category: str) -> str:
    return CATEGORY_ICON.get(category, DEFAULT_ICON)


def color(category: str) -> str:
    return CATEGORY_COLOR.get(category, DEFAULT_COLOR)
