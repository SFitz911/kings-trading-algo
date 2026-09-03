"""Background trading loop: poll 5H bars, evaluate RSI crossover, place orders."""
from __future__ import annotations

import csv
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from .broker import CHART_LOOKBACK, SIGNAL_LOOKBACK, Broker
from .config import TRADE_LOG_PATH, Config
from .strategy import Signal, decide, rsi

MAX_EVENTS = 200
PRICE_TICK_SECONDS = 3
COST_BUFFER = 1.002  # headroom so a market order does not slip past buying power
MIN_NOTIONAL = 1.0


@dataclass
class BotState:
    """Snapshot handed to the GUI on every poll. Rebuilt, never mutated in place."""
    running: bool = False
    connected: bool = False
    price: float = 0.0
    rsi: float = 0.0
    equity: float = 0.0
    position_qty: float = 0.0
    avg_entry: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    last_signal: str = Signal.HOLD.value
    last_bar_time: str = "--"
    error: str = ""
    bars: pd.DataFrame | None = None
    rsi_series: pd.Series | None = None
    # Provisional values for the bar still forming. Shown on the charts as a live
    # dashed extension; never used for signals, which only read closed bars.
    rsi_live: float = 0.0
    forming_time: pd.Timestamp | None = None
    events: list[str] = field(default_factory=list)


class TradingEngine:
    """Owns the polling thread. `on_update` is called with a fresh BotState."""

    def __init__(self, config: Config, on_update: Callable[[BotState], None]) -> None:
        self._config = config
        self._on_update = on_update
        self._broker = Broker(config)
        self._stop = threading.Event()
        self._stop_ticker = threading.Event()
        self._thread: threading.Thread | None = None
        self._ticker: threading.Thread | None = None
        self._events: list[str] = []
        self._last_traded_bar: pd.Timestamp | None = None
        self._bar_length = pd.Timedelta(minutes=config.signal_minutes)
        self._signal_close: pd.Series | None = None
        self.state = BotState()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def run_once(self) -> BotState:
        """Single evaluate-and-trade pass for scheduled/headless runs.

        Safe to re-run on a schedule: the open position is read from the broker
        rather than held in memory, so a repeat run on the same bar will not
        re-enter a trade it has already taken.
        """
        self._poll(trade=True)
        return self.state

    def start_price_feed(self) -> None:
        """Fast loop for live price and unrealized P&L, independent of the bar poll
        so numbers keep moving whether or not the strategy is running."""
        if self._ticker and self._ticker.is_alive():
            return
        self._stop_ticker.clear()
        self._ticker = threading.Thread(target=self._tick_loop, daemon=True)
        self._ticker.start()

    def shutdown(self) -> None:
        self.stop()
        self._stop_ticker.set()

    def _tick_loop(self) -> None:
        while not self._stop_ticker.is_set():
            try:
                self._tick()
            except Exception as error:
                print(f"price tick failed: {error}")
            self._stop_ticker.wait(PRICE_TICK_SECONDS)

    def _tick(self) -> None:
        """Refresh price and P&L only; bars, RSI and signals are left untouched."""
        position = self._broker.position()
        price = self._broker.latest_price()
        # Marked against the live trade price rather than Alpaca's slower position
        # mark, so the number moves on every tick.
        pnl = (price - position.avg_entry) * position.qty if position.qty else 0.0
        cost = position.avg_entry * position.qty
        live = {}
        if self.state.rsi_series is not None:
            rsi_live, forming_time = self._provisional(self._signal_close, price)
            live = {"rsi_live": rsi_live, "forming_time": forming_time}
        self.state = BotState(**{
            **self.state.__dict__,
            **live,
            "connected": True,
            "running": self.is_running,
            "events": list(self._events),
            "price": price,
            "position_qty": position.qty,
            "avg_entry": position.avg_entry,
            "unrealized_pnl": pnl,
            "unrealized_pnl_pct": (pnl / cost * 100) if cost else 0.0,
        })
        self._on_update(self.state)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def blitz(self) -> str:
        """Manual test trade, independent of the RSI signal: buy when flat,
        close the position when long. Returns the side that was sent."""
        bars = self._broker.bars(self._config.signal_minutes, SIGNAL_LOOKBACK)
        qty = self._broker.position_qty()
        price = float(bars["close"].iloc[-1])
        rsi_now = float(rsi(bars["close"].iloc[:-1], self._config.rsi_period).dropna().iloc[-1])
        side = Signal.SELL if qty > 0 else Signal.BUY
        self._log(f"BLITZ manual {side.value}")
        self._execute(side, qty, price, rsi_now)
        # Refresh the dashboard; do not let a manual click trigger a signal trade.
        self._poll(trade=self.is_running)
        return side.value

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

    def _provisional(self, closed_close: pd.Series, price: float) -> tuple[float, pd.Timestamp]:
        """RSI as it stands mid-bar, treating `price` as the forming bar's close."""
        forming_time = closed_close.index[-1] + self._bar_length
        series = pd.concat([closed_close, pd.Series([price], index=[forming_time])])
        return float(rsi(series, self._config.rsi_period).dropna().iloc[-1]), forming_time

    def log_error(self, message: str) -> None:
        """Surface a failure from outside the polling loop (e.g. a manual trade)."""
        self._log(f"ERROR: {message}")
        self.state = BotState(
            **{**self.state.__dict__, "error": message, "events": list(self._events)}
        )
        self._on_update(self.state)

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

    def _poll(self, trade: bool = True) -> None:
        bars = self._broker.bars(self._config.signal_minutes, SIGNAL_LOOKBACK)
        # The newest bar is still forming; only completed candles produce signals.
        closed = bars.iloc[:-1]
        chart_bars = self._broker.bars(self._config.chart_minutes, CHART_LOOKBACK)
        rsi_series = rsi(closed["close"], self._config.rsi_period)
        position = self._broker.position()
        qty = position.qty
        price = float(bars["close"].iloc[-1])
        bar_time = closed.index[-1]

        self._signal_close = closed["close"]
        rsi_live, forming_time = self._provisional(closed["close"], price)

        signal = decide(rsi_series, qty > 0, self._config.rsi_entry, self._config.rsi_exit)
        if trade and signal is not Signal.HOLD and bar_time != self._last_traded_bar:
            self._last_traded_bar = bar_time
            qty = self._execute(signal, qty, price, float(rsi_series.dropna().iloc[-1]))

        self.state = BotState(
            running=self.is_running,
            connected=True,
            price=price,
            rsi=float(rsi_series.dropna().iloc[-1]),
            equity=self._broker.account_equity(),
            position_qty=qty,
            avg_entry=position.avg_entry,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_pct=position.unrealized_pnl_pct,
            last_signal=signal.value,
            last_bar_time=bar_time.strftime("%Y-%m-%d %H:%M UTC"),
            error="",
            bars=chart_bars,
            rsi_series=rsi_series,
            rsi_live=rsi_live,
            forming_time=forming_time,
            events=list(self._events),
        )
        self._on_update(self.state)

    def _execute(self, signal: Signal, qty: float, price: float, rsi_value: float) -> float:
        if signal is Signal.BUY:
            return self._buy(price, rsi_value, qty)

        self._broker.sell(qty)
        self._log(f"SELL {qty:.6f} @ ~${price:,.2f} (RSI {rsi_value:.1f})")
        self._record_trade("SELL", qty, price, rsi_value)
        return 0.0

    def _buy(self, price: float, rsi_value: float, current_qty: float) -> float:
        """Buy one whole token when affordable; otherwise fall back to spending
        a fixed percentage of account equity."""
        target = self._config.target_qty
        buying_power = self._broker.buying_power()

        if buying_power >= target * price * COST_BUFFER:
            self._broker.buy_qty(target)
            self._log(f"BUY  {target:g} {self._config.symbol.split('/')[0]} "
                      f"@ ~${price:,.2f} (RSI {rsi_value:.1f})")
            self._record_trade("BUY", target, price, rsi_value)
            return target

        notional = min(self._broker.account_equity() * self._config.fallback_equity_pct,
                       buying_power / COST_BUFFER)
        if notional < MIN_NOTIONAL:
            self._log(f"BUY skipped: buying power ${buying_power:,.2f} too low")
            return current_qty

        self._broker.buy_notional(notional)
        percent = self._config.fallback_equity_pct * 100
        self._log(f"BUY  ${notional:,.2f} ({percent:g}% of equity - cannot afford "
                  f"{target:g} whole) @ ~${price:,.2f} (RSI {rsi_value:.1f})")
        self._record_trade("BUY", notional / price, price, rsi_value)
        return notional / price
