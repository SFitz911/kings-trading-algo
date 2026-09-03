"""RSI calculation and long-only crossover signal logic."""
from __future__ import annotations

from enum import Enum

import pandas as pd

MIN_BARS_MULTIPLIER = 3


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI, returned as a series aligned to `close`."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    return (100 - (100 / (1 + rs))).fillna(100.0).where(avg_gain.notna())


def decide(
    rsi_series: pd.Series,
    is_long: bool,
    entry_level: float,
    exit_level: float,
) -> Signal:
    """Long-only crossover: enter when RSI crosses up through `entry_level`,
    exit when it crosses down through `exit_level`. Never shorts."""
    clean = rsi_series.dropna()
    if len(clean) < 2:
        return Signal.HOLD

    previous, current = float(clean.iloc[-2]), float(clean.iloc[-1])

    if not is_long and previous <= entry_level < current:
        return Signal.BUY
    if is_long and previous >= exit_level > current:
        return Signal.SELL
    return Signal.HOLD
