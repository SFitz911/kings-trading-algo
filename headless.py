"""Headless single-pass runner for scheduled hosting (GitHub Actions, cron, etc).

Evaluates the RSI crossover once against the latest closed 5H bar, places an
order if the signal calls for it, prints a summary and exits. No display needed.
"""
from __future__ import annotations

import sys

from kings_algo.config import load_config
from kings_algo.engine import TradingEngine


def main() -> int:
    config = load_config()
    engine = TradingEngine(config, lambda _state: None)

    try:
        state = engine.run_once()
    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1

    position = f"{state.position_qty:.8f}" if state.position_qty else "flat"
    print(f"symbol        {config.symbol}")
    print(f"bar           {state.last_bar_time}")
    print(f"price         ${state.price:,.2f}")
    print(f"rsi({config.rsi_period})        {state.rsi:.2f}  "
          f"(entry {config.rsi_entry:g} / exit {config.rsi_exit:g})")
    print(f"signal        {state.last_signal}")
    print(f"position      {position}")
    if state.position_qty:
        print(f"entry         ${state.avg_entry:,.2f}")
        print(f"unrealized    ${state.unrealized_pnl:,.2f} "
              f"({state.unrealized_pnl_pct:+.2f}%)")
    print(f"equity        ${state.equity:,.2f}")

    for event in state.events:
        print(event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
