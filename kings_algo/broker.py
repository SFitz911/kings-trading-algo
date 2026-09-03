"""Thin wrapper over the Alpaca paper-trading and crypto data APIs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from .config import Config

BAR_TIMEFRAME = TimeFrame(5, TimeFrameUnit.Hour)
HISTORY_DAYS = 60


class Broker:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._data = CryptoHistoricalDataClient(config.api_key, config.secret_key)
        self._trading = TradingClient(config.api_key, config.secret_key, paper=True)

    def bars(self) -> pd.DataFrame:
        """5-hour OHLCV bars for the configured symbol, oldest first."""
        request = CryptoBarsRequest(
            symbol_or_symbols=[self._config.symbol],
            timeframe=BAR_TIMEFRAME,
            start=datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS),
        )
        frame = self._data.get_crypto_bars(request).df
        if frame.empty:
            raise RuntimeError(f"No bars returned for {self._config.symbol}")
        return frame.reset_index().set_index("timestamp").sort_index()

    def position_qty(self) -> float:
        """Open long quantity for the symbol, or 0.0 when flat."""
        key = self._config.symbol.replace("/", "")
        for position in self._trading.get_all_positions():
            if position.symbol.replace("/", "") == key:
                return float(position.qty)
        return 0.0

    def account_equity(self) -> float:
        return float(self._trading.get_account().equity)

    def buy(self, notional: float):
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
