"""Configuration loaded from the .env file at the project root."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

TRADE_LOG_PATH = PROJECT_ROOT / "trades.csv"


@dataclass(frozen=True)
class Config:
    api_key: str
    secret_key: str
    symbol: str
    signal_minutes: int
    chart_minutes: int
    rsi_period: int
    rsi_entry: float
    rsi_exit: float
    target_qty: float
    fallback_equity_pct: float
    poll_seconds: int


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing {name} in .env (copy .env.example to .env and fill it in)")
    return value


def load_config() -> Config:
    return Config(
        api_key=_require("ALPACA_API_KEY"),
        secret_key=_require("ALPACA_SECRET_KEY"),
        symbol=os.getenv("SYMBOL", "BTC/USD"),
        signal_minutes=int(os.getenv("SIGNAL_MINUTES", "15")),
        chart_minutes=int(os.getenv("CHART_MINUTES", "1")),
        rsi_period=int(os.getenv("RSI_PERIOD", "14")),
        rsi_entry=float(os.getenv("RSI_ENTRY", "50")),
        rsi_exit=float(os.getenv("RSI_EXIT", "50")),
        target_qty=float(os.getenv("TARGET_QTY", "1")),
        fallback_equity_pct=float(os.getenv("FALLBACK_EQUITY_PCT", "0.75")),
        poll_seconds=int(os.getenv("POLL_SECONDS", "60")),
    )
