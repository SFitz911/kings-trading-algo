"""Thin wrapper over the Alpaca paper-trading and crypto data APIs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dataclasses import dataclass

import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest, CryptoLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from .config import Config

SIGNAL_LOOKBACK = timedelta(days=5)
CHART_LOOKBACK = timedelta(hours=8)


@dataclass(frozen=True)
class Position:
    """Open long position, or the flat placeholder from `Position.flat()`."""
    qty: float
    avg_entry: float
    unrealized_pnl: float
    unrealized_pnl_pct: float

    @staticmethod
    def flat() -> "Position":
        return Position(0.0, 0.0, 0.0, 0.0)


class Broker:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._data = CryptoHistoricalDataClient(config.api_key, config.secret_key)
        self._trading = TradingClient(config.api_key, config.secret_key, paper=True)

    def bars(self, minutes: int, lookback: timedelta) -> pd.DataFrame:
        """OHLCV bars at the given minute timeframe, oldest first."""
        request = CryptoBarsRequest(
            symbol_or_symbols=[self._config.symbol],
            timeframe=TimeFrame(minutes, TimeFrameUnit.Minute),
            start=datetime.now(timezone.utc) - lookback,
        )
        frame = self._data.get_crypto_bars(request).df
        if frame.empty:
            raise RuntimeError(f"No bars returned for {self._config.symbol}")
        return frame.reset_index().set_index("timestamp").sort_index()

    def latest_price(self) -> float:
        """Live mark for tick-by-tick P&L. Uses the quote midpoint: trades on this
        feed can be minutes stale, while quotes refresh continuously."""
        request = CryptoLatestQuoteRequest(symbol_or_symbols=[self._config.symbol])
        quote = self._data.get_crypto_latest_quote(request)[self._config.symbol]
        bid, ask = float(quote.bid_price), float(quote.ask_price)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
        return bid or ask

    def position(self) -> Position:
        """Open long position for the symbol, or a flat placeholder."""
        key = self._config.symbol.replace("/", "")
        for open_position in self._trading.get_all_positions():
            if open_position.symbol.replace("/", "") == key:
                return Position(
                    qty=float(open_position.qty),
                    avg_entry=float(open_position.avg_entry_price),
                    unrealized_pnl=float(open_position.unrealized_pl or 0.0),
                    unrealized_pnl_pct=float(open_position.unrealized_plpc or 0.0) * 100,
                )
        return Position.flat()

    def position_qty(self) -> float:
        return self.position().qty

    def account_equity(self) -> float:
        return float(self._trading.get_account().equity)

    def buying_power(self) -> float:
        account = self._trading.get_account()
        return float(account.non_marginable_buying_power or account.buying_power)

    def buy_qty(self, qty: float):
        return self._trading.submit_order(
            MarketOrderRequest(
                symbol=self._config.symbol,
                qty=round(qty, 8),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
            )
        )

    def buy_notional(self, notional: float):
        return self._trading.submit_order(
            MarketOrderRequest(
                symbol=self._config.symbol,
                notional=round(notional, 2),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
            )
        )

    def sell(self, qty: float):
        return self._trading.submit_order(
            MarketOrderRequest(
                symbol=self._config.symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
            )
        )
