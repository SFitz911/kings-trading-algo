"""Dark terminal-desk palette and matplotlib styling for the dashboard."""
from __future__ import annotations

BG = "#0d1117"
PANEL = "#151b23"
BORDER = "#232c38"
TEXT = "#e6edf3"
MUTED = "#7d8894"
GREEN = "#3fb950"
RED = "#f85149"
AMBER = "#d29922"
ACCENT = "#58a6ff"

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_LABEL = ("Segoe UI", 8)
FONT_STAT = ("Consolas", 20, "bold")
FONT_TITLE = ("Segoe UI Semibold", 15)
FONT_MONO = ("Consolas", 9)

MPL_STYLE = {
    "figure.facecolor": BG,
    "axes.facecolor": PANEL,
    "axes.edgecolor": BORDER,
    "axes.labelcolor": MUTED,
    "text.color": TEXT,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "grid.color": BORDER,
    "font.size": 8,
}
