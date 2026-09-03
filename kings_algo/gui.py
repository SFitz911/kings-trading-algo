"""Tkinter dashboard for the Kings Trading Algo bot."""
from __future__ import annotations

import queue
import threading
import tkinter as tk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from . import theme
from .config import Config
from .engine import BotState, TradingEngine

REFRESH_MS = 200
CHART_BARS = 120
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

STAT_CARDS = ("price", "rsi", "position", "equity", "signal")


class Dashboard(tk.Tk):
    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._queue: queue.Queue[BotState] = queue.Queue()
        self._engine = TradingEngine(config, self._queue.put)

        self.title("Kings Trading Algo - BTC/USD - RSI 5H Crossover")
        self.geometry("1180x760")
        self.minsize(940, 640)
        self.configure(bg=theme.BG)

        self._stats: dict[str, tk.Label] = {}
        self._build_header()
        self._build_stats()
        self._build_body()
        self._render(self._engine.state)
        self.after(REFRESH_MS, self._drain)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- layout ------------------------------------------------------------
    def _build_header(self) -> None:
        bar = tk.Frame(self, bg=theme.BG)
        bar.pack(fill="x", padx=18, pady=(16, 8))

        tk.Label(bar, text="KINGS TRADING ALGO", font=theme.FONT_TITLE,
                 bg=theme.BG, fg=theme.TEXT).pack(side="left")
        subtitle = (f"   {self._config.symbol}  /  5H RSI-{self._config.rsi_period}"
                    f"  /  long only  /  PAPER")
        tk.Label(bar, text=subtitle, font=theme.FONT_SMALL,
                 bg=theme.BG, fg=theme.MUTED).pack(side="left", padx=(10, 0))

        self._stop_button = tk.Button(bar, text="STOP", width=10, command=self._stop,
                                      bg=theme.PANEL, fg=theme.RED, font=theme.FONT,
                                      relief="flat", activebackground=theme.BORDER,
                                      activeforeground=theme.RED, state="disabled")
        self._stop_button.pack(side="right", padx=(8, 0))
        self._start_button = tk.Button(bar, text="START BOT", width=12, command=self._start,
                                       bg=theme.GREEN, fg=theme.BG, font=theme.FONT,
                                       relief="flat", activebackground=theme.GREEN)
        self._start_button.pack(side="right")

        self._blitz_button = tk.Button(bar, text="BLITZ TEST BUY", width=16,
                                       command=self._blitz, bg=theme.PURPLE, fg=theme.BG,
                                       font=theme.FONT, relief="flat",
                                       activebackground=theme.PURPLE)
        self._blitz_button.pack(side="right", padx=(0, 16))

        self._status = tk.Label(bar, text="- idle", font=theme.FONT_SMALL,
                                bg=theme.BG, fg=theme.MUTED)
        self._status.pack(side="right", padx=(0, 16))

    def _build_stats(self) -> None:
        labels = {
            "price": "BTC PRICE",
            "rsi": f"RSI({self._config.rsi_period}) 5H",
            "position": "POSITION",
            "equity": "EQUITY",
            "signal": "LAST SIGNAL",
        }
        row = tk.Frame(self, bg=theme.BG)
        row.pack(fill="x", padx=18)
        for index, key in enumerate(STAT_CARDS):
            row.columnconfigure(index, weight=1)
            card = tk.Frame(row, bg=theme.PANEL, highlightbackground=theme.BORDER,
                            highlightthickness=1)
            card.grid(row=0, column=index, sticky="ew",
                      padx=(0 if index == 0 else 8, 0))
            tk.Label(card, text=labels[key], font=theme.FONT_LABEL, bg=theme.PANEL,
                     fg=theme.MUTED).pack(anchor="w", padx=14, pady=(10, 0))
            value = tk.Label(card, text="--", font=theme.FONT_STAT,
                             bg=theme.PANEL, fg=theme.TEXT)
            value.pack(anchor="w", padx=14, pady=(0, 12))
            self._stats[key] = value

    def _build_body(self) -> None:
        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        with matplotlib.rc_context(theme.MPL_STYLE):
            self._figure = Figure(figsize=(7, 5), dpi=100)
            self._price_axes = self._figure.add_subplot(2, 1, 1)
            self._rsi_axes = self._figure.add_subplot(2, 1, 2, sharex=self._price_axes)
            self._figure.subplots_adjust(left=0.10, right=0.98, top=0.96,
                                         bottom=0.10, hspace=0.18)
        chart = FigureCanvasTkAgg(self._figure, master=body)
        chart.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._chart = chart

        side = tk.Frame(body, bg=theme.PANEL, highlightbackground=theme.BORDER,
                        highlightthickness=1)
        side.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        tk.Label(side, text="ACTIVITY", font=theme.FONT_LABEL, bg=theme.PANEL,
                 fg=theme.MUTED).pack(anchor="w", padx=12, pady=(10, 6))
        self._log = tk.Text(side, bg=theme.PANEL, fg=theme.TEXT, font=theme.FONT_MONO,
                            relief="flat", wrap="word", state="disabled",
                            insertbackground=theme.TEXT)
        self._log.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self._log.tag_configure("buy", foreground=theme.GREEN)
        self._log.tag_configure("sell", foreground=theme.AMBER)
        self._log.tag_configure("error", foreground=theme.RED)
        self._log.tag_configure("info", foreground=theme.MUTED)

    # -- controls ----------------------------------------------------------
    def _start(self) -> None:
        self._engine.start()
        self._start_button.configure(state="disabled")
        self._stop_button.configure(state="normal")
        self._status.configure(text="- connecting", fg=theme.AMBER)

    def _stop(self) -> None:
        self._engine.stop()
        self._start_button.configure(state="normal")
        self._stop_button.configure(state="disabled")
        self._status.configure(text="- stopped", fg=theme.MUTED)

    def _blitz(self) -> None:
        """Fire a manual buy/sell off the UI thread so the window stays responsive."""
        self._blitz_button.configure(state="disabled", text="SENDING...")
        threading.Thread(target=self._blitz_worker, daemon=True).start()

    def _blitz_worker(self) -> None:
        try:
            self._engine.blitz()
        except Exception as error:
            self._engine.log_error(f"BLITZ failed: {error}")
        finally:
            self.after(0, lambda: self._blitz_button.configure(state="normal"))

    def _on_close(self) -> None:
        self._engine.stop()
        self.destroy()

    # -- rendering ---------------------------------------------------------
    def _drain(self) -> None:
        state = None
        while not self._queue.empty():
            state = self._queue.get_nowait()
        if state is not None:
            self._render(state)
        self.after(REFRESH_MS, self._drain)

    def _render(self, state: BotState) -> None:
        self._stats["price"].configure(text=f"${state.price:,.0f}" if state.price else "--")
        rsi_color = theme.GREEN if state.rsi >= self._config.rsi_entry else theme.RED
        self._stats["rsi"].configure(text=f"{state.rsi:.1f}" if state.rsi else "--",
                                     fg=rsi_color if state.rsi else theme.TEXT)
        self._stats["position"].configure(
            text=f"{state.position_qty:.5f}" if state.position_qty else "FLAT",
            fg=theme.GREEN if state.position_qty else theme.MUTED)
        self._stats["equity"].configure(text=f"${state.equity:,.0f}" if state.equity else "--")
        self._stats["signal"].configure(
            text=state.last_signal,
            fg={"BUY": theme.GREEN, "SELL": theme.AMBER}.get(state.last_signal, theme.MUTED))

        if self._blitz_button["state"] != "disabled":
            self._blitz_button.configure(
                text="BLITZ TEST SELL" if state.position_qty else "BLITZ TEST BUY")

        if state.error:
            self._status.configure(text="- error", fg=theme.RED)
        elif state.connected:
            self._status.configure(text=f"- live / bar {state.last_bar_time}", fg=theme.GREEN)

        self._render_log(state.events)
        if state.bars is not None and state.rsi_series is not None:
            self._render_charts(state)

    def _render_log(self, events: list[str]) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        for event in reversed(events):
            if "ERROR" in event:
                tag = "error"
            elif "BUY" in event:
                tag = "buy"
            elif "SELL" in event:
                tag = "sell"
            else:
                tag = "info"
            self._log.insert("end", event + "\n\n", tag)
        self._log.configure(state="disabled")

    def _render_charts(self, state: BotState) -> None:
        bars = state.bars.tail(CHART_BARS)
        rsi_values = state.rsi_series.tail(CHART_BARS)

        with matplotlib.rc_context(theme.MPL_STYLE):
            self._price_axes.clear()
            self._price_axes.plot(bars.index, bars["close"], color=theme.ACCENT, linewidth=1.4)
            self._price_axes.fill_between(bars.index, bars["close"].min(), bars["close"],
                                          color=theme.ACCENT, alpha=0.08)
            self._price_axes.set_ylabel(f"{self._config.symbol}  (5H close)")
            self._price_axes.grid(alpha=0.25, linewidth=0.5)
            self._price_axes.tick_params(labelbottom=False)

            self._rsi_axes.clear()
            self._rsi_axes.plot(rsi_values.index, rsi_values, color=theme.TEXT, linewidth=1.2)
            # Fixed reference bands: overbought 70 in red, oversold 30 in green.
            self._rsi_axes.axhline(RSI_OVERBOUGHT, color=theme.RSI_UPPER, linewidth=0.7)
            self._rsi_axes.axhline(RSI_OVERSOLD, color=theme.RSI_LOWER, linewidth=0.7)
            # The levels the bot actually trades, when they differ from the bands.
            for level in {self._config.rsi_entry, self._config.rsi_exit}:
                if level not in (RSI_OVERBOUGHT, RSI_OVERSOLD):
                    self._rsi_axes.axhline(level, color=theme.PURPLE, linestyle=":",
                                           linewidth=0.8, alpha=0.7)
            self._rsi_axes.set_yticks([0, RSI_OVERSOLD, 50, RSI_OVERBOUGHT, 100])
            self._rsi_axes.set_ylim(0, 100)
            self._rsi_axes.set_ylabel(f"RSI {self._config.rsi_period}")
            self._rsi_axes.grid(alpha=0.25, linewidth=0.5)
        self._chart.draw_idle()
