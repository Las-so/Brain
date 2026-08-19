"""
ROBINHOOD LIVE SCAN ADAPTER
----------------------------
Feeds OHLCV bars fetched from Robinhood (via its MCP tools, by the Claude
session driving the scheduled trading Routine) through the exact same
indicator/pattern/divergence logic used by aristotle_alert_system.py, so
the live-trading path and the alert-only path never disagree about what
counts as a signal.

This script makes no network calls itself and places no orders -- it reads
already-fetched OHLCV bars from a JSON file and prints a structured
verdict. The caller is responsible for fetching the bars (get_equity_historicals),
running this script, and deciding what to do with the result -- sizing via
robinhood_risk.position_size() and proposing (never silently placing) an
order via review_equity_order.

Input JSON shape:
{
  "symbol": "SPY",
  "timeframes": {
    "Weekly": [{"open": .., "high": .., "low": .., "close": ..}, ...],
    "Daily":  [{"open": .., "high": .., "low": .., "close": ..}, ...]
  }
}
Bars must be in chronological order (oldest first), at least 30 per
timeframe (200+ recommended on Daily for a meaningful 200-EMA).

Usage:
    python robinhood_scan.py bars.json
"""

import json
import sys

import pandas as pd

from aristotle_alert_system import (
    add_indicators,
    detect_divergence,
    fib_golden_pocket,
    is_bearish_engulfing,
    is_bearish_pin_bar,
    is_bullish_engulfing,
    is_bullish_pin_bar,
)


def evaluate_timeframe(bars):
    """Same trend/RSI/pattern/divergence logic as scan_ticker(), applied to
    caller-supplied bars instead of a yfinance fetch. Returns None if there
    isn't enough history for a meaningful reading."""
    if len(bars) < 30:
        return None

    df = add_indicators(pd.DataFrame(bars))
    last = df.iloc[-1]
    fibs = fib_golden_pocket(df)

    trend = "BULLISH" if last["close"] > last["ema200"] else "BEARISH"
    bull_engulf = is_bullish_engulfing(df)
    bear_engulf = is_bearish_engulfing(df)
    bull_pin = is_bullish_pin_bar(df)
    bear_pin = is_bearish_pin_bar(df)
    rsi_divergence = detect_divergence(df, "rsi14")
    macd_divergence = detect_divergence(df, "macd_hist")
    in_golden_pocket = fibs["golden_pocket_low"] <= last["close"] <= fibs["golden_pocket_high"]

    return {
        "trend": trend,
        "rsi14": None if pd.isna(last["rsi14"]) else round(float(last["rsi14"]), 2),
        "bull_signal": bool(
            bull_engulf or bull_pin or rsi_divergence == "bullish" or macd_divergence == "bullish"
        ),
        "bear_signal": bool(
            bear_engulf or bear_pin or rsi_divergence == "bearish" or macd_divergence == "bearish"
        ),
        "in_golden_pocket": bool(in_golden_pocket),
        "last_close": float(last["close"]),
        "last_high": float(last["high"]),
        "last_low": float(last["low"]),
    }


def evaluate(symbol, timeframes):
    """Confluence verdict across whatever timeframes were supplied, matching
    aristotle_alert_system.scan_ticker's rule: a bull signal on at least one
    timeframe, with a majority (>=2) of available timeframes trending
    bullish. With Weekly+Daily (the two Robinhood makes easy to fetch
    server-side-indicator-computed), that means both must agree."""
    results = {label: evaluate_timeframe(bars) for label, bars in timeframes.items()}
    results = {label: r for label, r in results.items() if r is not None}

    bull_count = sum(1 for r in results.values() if r["trend"] == "BULLISH")
    bull_signal_timeframes = [tf for tf, r in results.items() if r["bull_signal"]]

    confluence_bull = bool(bull_signal_timeframes) and bull_count >= 2

    verdict = {
        "symbol": symbol,
        "timeframes": results,
        "confluence_bull": confluence_bull,
        "bull_signal_timeframes": bull_signal_timeframes,
    }

    daily = results.get("Daily")
    if confluence_bull and daily:
        entry = round(daily["last_high"] + 0.15, 2)
        stop = round(daily["last_low"], 2)
        verdict["suggested_entry"] = entry
        verdict["suggested_stop"] = stop
        verdict["risk_per_share"] = round(entry - stop, 2)

    return verdict


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        data = json.load(f)
    print(json.dumps(evaluate(data["symbol"], data["timeframes"]), indent=2))
