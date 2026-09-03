"""Background trading loop: poll 5H bars, evaluate RSI crossover, place orders."""
from __future__ import annotations

import csv
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from .broker import Broker
from .config import TRADE_LOG_PATH, Config
from .strategy import Signal, decide, rsi

MAX_EVENTS = 200


@dataclass
class BotState:
    """Snapshot handed to the GUI on every poll. Rebuilt, never mutated in place."""
    running: bool = False
    connected: bool = False
    price: float = 0.0
    rsi: float = 0.0
    equity: float = 0.0
    position_qty: float = 0.0
    last_signal: str = Signal.HOLD.value
    last_bar_time: str = "--"
    error: str = ""
    bars: pd.DataFrame | None = None
    rsi_series: pd.Series | None = None
    events: list[str] = field(default_factory=list)


class TradingEngine:
    """Owns the polling thread. `on_update` is called with a fresh BotState."""

    def __init__(self, config: Config, on_update: Callable[[BotState], None]) -> None:
        self._config = config
        self._on_update = on_update
        self._broker = Broker(config)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._events: list[str] = []
        self._last_traded_bar: pd.Timestamp | None = None
        self.state = BotState()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._log("Bot stopped by user")
        self.state = BotState(**{**self.state.__dict__, "running": False})
        self._on_update(self.state)

    # -- internals ---------------------------------------------------------
    def _log(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self._events.append(f"[{stamp}Z] {message}")
        del self._events[:-MAX_EVENTS]

    def _record_trade(self, side: str, qty: float, price: float, rsi_value: float) -> None:
        is_new = not TRADE_LOG_PATH.exists()
        with TRADE_LOG_PATH.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if is_new:
                writer.writerow(["timestamp_utc", "symbol", "side", "qty", "price", "rsi"])
            writer.writerow([
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                self._config.symbol, side, f"{qty:.8f}", f"{price:.2f}", f"{rsi_value:.2f}",
            ])

    def _run(self) -> None:
        self._log(f"Bot started on {self._config.symbol} (5H RSI-{self._config.rsi_period} crossover, long only)")
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception as error:  # keep the loop alive; surface it in the GUI
                self._log(f"ERROR: {error}")
                traceback.print_exc()
                self.state = BotState(
                    **{**self.state.__dict__, "connected": False,
                       "error": str(error), "events": list(self._events)}
                )
                self._on_update(self.state)
            self._stop.wait(self._config.poll_seconds)

    def _poll(self) -> None:
        bars = self._broker.bars()
        # The newest bar is still forming; only completed 5H candles produce signals.
        closed = bars.iloc[:-1]
        rsi_series = rsi(closed["close"], self._config.rsi_period)
        qty = self._broker.position_qty()
        price = float(bars["close"].iloc[-1])
        bar_time = closed.index[-1]

        signal = decide(rsi_series, qty > 0, self._config.rsi_entry, self._config.rsi_exit)
        if signal is not Signal.HOLD and bar_time != self._last_traded_bar:
            self._last_traded_bar = bar_time
            qty = self._execute(signal, qty, price, float(rsi_series.dropna().iloc[-1]))

        self.state = BotState(
            running=True,
            connected=True,
            price=price,
            rsi=float(rsi_series.dropna().iloc[-1]),
            equity=self._broker.account_equity(),
            position_qty=qty,
            last_signal=signal.value,
            last_bar_time=bar_time.strftime("%Y-%m-%d %H:%M UTC"),
            error="",
            bars=closed,
            rsi_series=rsi_series,
            events=list(self._events),
        )
        self._on_update(self.state)

    def _execute(self, signal: Signal, qty: float, price: float, rsi_value: float) -> float:
        if signal is Signal.BUY:
            notional = min(self._config.order_notional, self._broker.account_equity() * 0.95)
            if notional < 1:
                self._log("BUY skipped: insufficient buying power")
                return qty
            self._broker.buy(notional)
            self._log(f"BUY  ${notional:,.2f} @ ~${price:,.2f} (RSI {rsi_value:.1f})")
            self._record_trade("BUY", notional / price, price, rsi_value)
            return notional / price

        self._broker.sell(qty)
        self._log(f"SELL {qty:.6f} @ ~${price:,.2f} (RSI {rsi_value:.1f})")
        self._record_trade("SELL", qty, price, rsi_value)
        return 0.0
