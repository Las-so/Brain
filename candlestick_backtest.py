#!/usr/bin/env python3
"""Backtest for the candlestick clone strategy (pin bar + engulfing, 15-cent rule).

Tests the UNDERLYING price-action edge, not option P&L (no historical option data).
Rules tested, per candlestick_clone_strategy.md:
  - Signal: bullish/bearish pin bar or engulfing on the daily, after a 3-candle
    counter-run, within 2% of a level (20-day extreme or the 200-day MA).
  - Entry: 15 cents beyond the signal candle extreme, triggered within 3 sessions.
  - Stop: opposite extreme of the signal candle.
  - Outcome: did price reach 2R before the stop? (max 30 sessions, else exit at close)

Usage: python candlestick_backtest.py [--years 3]
"""
import argparse
import sys

import pandas as pd
import yfinance as yf

UNIVERSE = [
    "SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "AMZN", "AMD", "META", "GOOGL",
    "MSFT", "PLTR", "SOFI", "NFLX", "DIS", "BA", "COP", "SLB", "UPS", "CRM",
    "NOW", "WDAY", "LYFT", "MARA", "RIOT", "COIN", "HOOD", "F", "INTC", "UBER",
]

WICK_RATIO = 2.0
LEVEL_PCT = 0.02
TRIGGER_WINDOW = 3
MAX_HOLD = 30
TICK = 0.15


def is_bull_pin(o, h, l, c, po=None):
    body_top, body_bot = max(o, c), min(o, c)
    lower_wick = body_bot - l
    body = max(body_top - body_bot, 1e-9)
    upper_wick = h - body_top
    return lower_wick >= WICK_RATIO * body and lower_wick > upper_wick


def is_bear_pin(o, h, l, c, po=None):
    body_top, body_bot = max(o, c), min(o, c)
    upper_wick = h - body_top
    body = max(body_top - body_bot, 1e-9)
    lower_wick = body_bot - l
    return upper_wick >= WICK_RATIO * body and upper_wick > lower_wick


def run(years: int) -> pd.DataFrame:
    trades = []
    period = f"{years}y"
    for ticker in UNIVERSE:
        try:
            df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        except Exception as e:  # noqa: BLE001
            print(f"{ticker}: download failed ({e})", file=sys.stderr)
            continue
        if df is None or len(df) < 220:
            continue
        df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
        df["ma200"] = df["close"].rolling(200).mean()
        df["lo20"] = df["low"].rolling(20).min()
        df["hi20"] = df["high"].rolling(20).max()

        o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
        ma, lo20, hi20 = df["ma200"].values, df["lo20"].values, df["hi20"].values

        for i in range(205, len(df) - 1):
            red_run = all(c[j] < o[j] for j in range(i - 3, i))
            green_run = all(c[j] > o[j] for j in range(i - 3, i))

            bull_engulf = (c[i - 1] < o[i - 1] and c[i] > o[i]
                           and o[i] <= c[i - 1] and c[i] >= o[i - 1])
            bear_engulf = (c[i - 1] > o[i - 1] and c[i] < o[i]
                           and o[i] >= c[i - 1] and c[i] <= o[i - 1])
            bull_pin = is_bull_pin(o[i], h[i], l[i], c[i])
            bear_pin = is_bear_pin(o[i], h[i], l[i], c[i])

            near_sup = (l[i] <= lo20[i - 1] * (1 + LEVEL_PCT)
                        or (not pd.isna(ma[i]) and abs(l[i] - ma[i]) / ma[i] <= LEVEL_PCT))
            near_res = (h[i] >= hi20[i - 1] * (1 - LEVEL_PCT)
                        or (not pd.isna(ma[i]) and abs(h[i] - ma[i]) / ma[i] <= LEVEL_PCT))

            sig = None
            if red_run and near_sup and (bull_pin or bull_engulf):
                sig = ("long", "pin" if bull_pin else "engulf")
            elif green_run and near_res and (bear_pin or bear_engulf):
                sig = ("short", "pin" if bear_pin else "engulf")
            if not sig:
                continue

            side, pattern = sig
            if side == "long":
                entry, stop = h[i] + TICK, l[i]
            else:
                entry, stop = l[i] - TICK, h[i]
            risk = abs(entry - stop)
            if risk <= 0.01:
                continue
            target = entry + 2 * risk if side == "long" else entry - 2 * risk

            # trigger within window
            t = None
            for j in range(i + 1, min(i + 1 + TRIGGER_WINDOW, len(df))):
                if (side == "long" and h[j] >= entry) or (side == "short" and l[j] <= entry):
                    t = j
                    break
            if t is None:
                continue

            # walk forward
            result, r_mult = None, None
            for j in range(t, min(t + MAX_HOLD, len(df))):
                lo_hit = l[j] <= stop if side == "long" else h[j] >= stop
                tg_hit = h[j] >= target if side == "long" else l[j] <= target
                if lo_hit and tg_hit:
                    result, r_mult = "stop_first_ambiguous", -1.0
                    break
                if lo_hit:
                    result, r_mult = "stopped", -1.0
                    break
                if tg_hit:
                    result, r_mult = "target_2R", 2.0
                    break
            if result is None:
                j = min(t + MAX_HOLD, len(df)) - 1
                r_mult = ((c[j] - entry) / risk) if side == "long" else ((entry - c[j]) / risk)
                result = "time_exit"

            trades.append({
                "ticker": ticker, "date": str(df.index[i].date()), "side": side,
                "pattern": pattern, "entry": round(entry, 2), "stop": round(stop, 2),
                "result": result, "R": round(r_mult, 2),
            })
    return pd.DataFrame(trades)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=3)
    args = ap.parse_args()
    df = run(args.years)
    if df.empty:
        print("No trades found.")
        return
    df.to_csv("candlestick_backtest_results.csv", index=False)
    print(f"Trades: {len(df)}  (universe {len(UNIVERSE)} tickers, {args.years}y daily)")
    for key in [None, "pattern", "side"]:
        groups = [("ALL", df)] if key is None else list(df.groupby(key))
        for name, g in groups:
            wins = (g["R"] >= 2).sum()
            losses = (g["R"] <= -1).sum()
            print(f"  {name:>8}: n={len(g):4d}  2R-win rate={wins/len(g):5.1%}  "
                  f"stopped={losses/len(g):5.1%}  avg R={g['R'].mean():+.2f}  "
                  f"total R={g['R'].sum():+.1f}")
    amb = (df["result"] == "stop_first_ambiguous").sum()
    print(f"  Ambiguous same-bar stop+target (counted as losses): {amb}")


if __name__ == "__main__":
    main()
