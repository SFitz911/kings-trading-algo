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
PURPLE = "#bc8cff"

# Chart axis text: high-contrast yellow so tick numbers read against the dark panel.
AXIS = "#f2cc60"
RSI_UPPER = "#f85149"  # 70 line
RSI_LOWER = "#3fb950"  # 30 line

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
    "axes.labelcolor": AXIS,
    "text.color": TEXT,
    "xtick.color": AXIS,
    "ytick.color": AXIS,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "grid.color": BORDER,
    "font.size": 8,
}
