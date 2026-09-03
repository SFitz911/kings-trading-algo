# Kings Trading Algo

A long-only Bitcoin trading bot for Alpaca **paper** accounts, with a live desktop dashboard.

- **Market:** `BTC/USD` on Alpaca crypto
- **Signal:** RSI(14) on 5-hour bars, crossover based
- **Direction:** long only — it never shorts
- **Execution:** market orders, notional-sized entries, full exit on the sell signal

## Strategy

Signals are evaluated only on **closed** 5-hour candles (the in-progress bar is ignored, so
signals never repaint):

| Condition | Action |
|---|---|
| RSI crosses **up** through `RSI_ENTRY` (default 50) while flat | BUY `TARGET_QTY` whole BTC |
| RSI crosses **down** through `RSI_EXIT` (default 50) while long | SELL the entire position |
| anything else | hold |

Set `RSI_ENTRY=30` / `RSI_EXIT=70` in `.env` if you want classic oversold/overbought bands
instead of the 50-line crossover.

## Setup

```bash
pip install -r requirements-gui.txt
cp .env.example .env    # then fill in your Alpaca paper keys
python run.py
```

Press **START BOT**. The dashboard polls every `POLL_SECONDS` (default 60) and shows price,
live RSI, position, unrealized P&L, account equity, the last signal, a 5H price/RSI chart,
and an activity log. Every fill is also appended to `trades.csv`.

**Position sizing:** each entry buys `TARGET_QTY` whole tokens (default 1 BTC). If buying power
cannot cover that, it falls back to spending `FALLBACK_EQUITY_PCT` of account equity instead.
Alpaca takes its crypto fee out of the received quantity, so a 1 BTC buy settles as ~0.9975 BTC.

**BLITZ TEST button:** sends a manual market buy ignoring the RSI signal; click again to close
the position. Useful for confirming the wiring end to end.

**Live P&L:** unrealized P&L is marked against the quote midpoint and refreshes every 3 seconds,
independently of the 5-hour bar poll.

## Configuration (`.env`)

| Key | Default | Meaning |
|---|---|---|
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | — | Alpaca paper credentials |
| `SYMBOL` | `BTC/USD` | traded pair |
| `RSI_PERIOD` | `14` | RSI lookback in 5H bars |
| `RSI_ENTRY` | `50` | cross-up level that opens a long |
| `RSI_EXIT` | `50` | cross-down level that closes it |
| `TARGET_QTY` | `1` | whole tokens to buy per entry |
| `FALLBACK_EQUITY_PCT` | `0.75` | fraction of equity spent when `TARGET_QTY` is unaffordable |
| `POLL_SECONDS` | `60` | poll interval |

## Hosting it 24/7

The strategy trades 5-hour candles, so it needs a *scheduled check*, not a process that
stays awake around the clock. [`.github/workflows/trade.yml`](.github/workflows/trade.yml)
runs [`headless.py`](headless.py) every 15 minutes on GitHub Actions — free on public repos.

Each run is a single evaluate-and-trade pass. Repeating it is safe because the open
position is read from Alpaca rather than held in memory, so a re-run on the same bar
will not double-enter.

To use it on your own fork, add two repository secrets under
**Settings → Secrets and variables → Actions**:

- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`

Everything else is set as plain env vars in the workflow. Trades appear in the run output
and are uploaded as a `trades.csv` artifact.

Two limits worth knowing: Actions cron is not punctual (GitHub delays runs under load,
sometimes 5–15 minutes), and scheduled workflows are disabled after 60 days of repository
inactivity. Neither matters on 5-hour bars. If you move to minute bars, switch to a
persistent worker on Render instead.

The dashboard stays local and reads live state from Alpaca, so you can open it any time to
see what the scheduled bot has been doing.

## Layout

```
run.py              dashboard entry point
headless.py         single-pass runner for scheduled hosting
kings_algo/
  config.py         .env loading
  strategy.py       RSI + crossover decision (pure functions)
  broker.py         Alpaca data + order wrapper
  engine.py         background polling/trading loop
  gui.py            Tkinter dashboard
  theme.py          palette and chart styling
```

## Notes

This targets Alpaca's **paper** endpoint and is hardcoded to `paper=True`. It is a learning /
experimentation project, not financial advice. Keep your real `.env` out of git — it is
already listed in `.gitignore`.
