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
| RSI crosses **up** through `RSI_ENTRY` (default 50) while flat | BUY `ORDER_NOTIONAL` worth of BTC |
| RSI crosses **down** through `RSI_EXIT` (default 50) while long | SELL the entire position |
| anything else | hold |

Set `RSI_ENTRY=30` / `RSI_EXIT=70` in `.env` if you want classic oversold/overbought bands
instead of the 50-line crossover.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # then fill in your Alpaca paper keys
python run.py
```

Press **START BOT**. The dashboard polls every `POLL_SECONDS` (default 60) and shows price,
live RSI, position, account equity, the last signal, a 5H price/RSI chart, and an activity log.
Every fill is also appended to `trades.csv`.

## Configuration (`.env`)

| Key | Default | Meaning |
|---|---|---|
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | — | Alpaca paper credentials |
| `SYMBOL` | `BTC/USD` | traded pair |
| `RSI_PERIOD` | `14` | RSI lookback in 5H bars |
| `RSI_ENTRY` | `50` | cross-up level that opens a long |
| `RSI_EXIT` | `50` | cross-down level that closes it |
| `ORDER_NOTIONAL` | `1000` | dollars per entry (capped at 95% of equity) |
| `POLL_SECONDS` | `60` | poll interval |

## Layout

```
run.py              entry point
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
