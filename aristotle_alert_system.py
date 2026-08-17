"""
ARISTOLE ALERT SYSTEM
---------------------
A watchlist scanner + position manager built around the Aristotle Investments /
"Trading Bondsman" framework: top-down multi-timeframe analysis, RSI/MACD
divergence, 8/21/200 EMA structure, Fibonacci golden pocket, pin bar / engulfing
detection, 15-cent entry rule, and R-multiple scale-out position management.

THIS SCRIPT DOES NOT PLACE TRADES. It only reads market data and prints/logs
alerts. You still pull the trigger. That's intentional -- alerting is where
automation earns its keep; execution is where a coded heuristic can quietly
cost you real money if a pattern-match is wrong.

SETUP
-----
pip install yfinance pandas numpy --break-system-packages

Then edit the WATCHLIST and POSITIONS sections below and run:
    python aristotle_alert_system.py

For real daily use, wire this into a cron job / scheduled task so it runs
automatically (e.g. 8:00am and 3:30pm ET) and pipes output to a file, email,
or a Slack/Discord webhook. That's the last step to make it "autonomous" --
this script is the brain, a scheduler is the heartbeat.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# =========================================================================
# CONFIG -- edit this section
# =========================================================================

WATCHLIST = ["SPY", "QQQ", "TSLA", "NVDA", "AAPL", "AMZN"]

# Open positions you want the system to track for scale-out / stop alerts.
# entry   = your average entry price
# stop    = your structural stop-loss level (low of setup candle, etc.)
# shares  = number of shares / contracts equivalent you hold RIGHT NOW
# targets = list of (R-multiple, fraction_of_ORIGINAL_position_to_sell)
#           e.g. (1.0, 0.33) means "at 1R profit, sell 33% of your original size"
# trail_after_R = once price passes this R-multiple, switch remaining shares
#                 to a trailing stop instead of a fixed target
POSITIONS = {
    # Example -- replace with your real positions or leave empty {}
    # "TSLA": {
    #     "entry": 250.00,
    #     "stop": 235.00,
    #     "shares": 30,
    #     "targets": [(1.0, 0.33), (2.0, 0.33)],
    #     "trail_after_R": 2.0,
    #     "trail_method": "21ema",   # "21ema", "8ema", or "swing_low"
    # },
}

# =========================================================================
# DATA FETCHING
# =========================================================================

def fetch(ticker, period="1y", interval="1d"):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty:
        return None
    df = df.rename(columns=str.lower)
    return df


# =========================================================================
# INDICATORS
# =========================================================================

def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def rsi(series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(length).mean()
    avg_loss = loss.rolling(length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series, fast=12, slow=26, signal=9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def add_indicators(df):
    df["ema8"] = ema(df["close"], 8)
    df["ema21"] = ema(df["close"], 21)
    df["ema200"] = ema(df["close"], 200)
    df["rsi14"] = rsi(df["close"])
    df["macd"], df["macd_signal"], df["macd_hist"] = macd(df["close"])
    return df


def fib_golden_pocket(df, lookback=60):
    """Golden pocket (61.8%-65%) of the most recent swing high->low (or low->high)."""
    window = df.tail(lookback)
    swing_high = window["high"].max()
    swing_low = window["low"].min()
    diff = swing_high - swing_low
    fib_618 = swing_high - diff * 0.618
    fib_650 = swing_high - diff * 0.65
    return {
        "swing_high": swing_high,
        "swing_low": swing_low,
        "golden_pocket_low": min(fib_618, fib_650),
        "golden_pocket_high": max(fib_618, fib_650),
    }


# =========================================================================
# CANDLESTICK PATTERN DETECTION (heuristic -- validate against your own eye)
# =========================================================================

def is_bullish_engulfing(df):
    if len(df) < 2:
        return False
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_red = prev["close"] < prev["open"]
    curr_green = curr["close"] > curr["open"]
    engulfs = curr["open"] <= prev["close"] and curr["close"] >= prev["open"]
    return bool(prev_red and curr_green and engulfs)


def is_bearish_engulfing(df):
    if len(df) < 2:
        return False
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_green = prev["close"] > prev["open"]
    curr_red = curr["close"] < curr["open"]
    engulfs = curr["open"] >= prev["close"] and curr["close"] <= prev["open"]
    return bool(prev_green and curr_red and engulfs)


def is_bullish_pin_bar(df, wick_ratio=2.0):
    """Long lower wick, small body near the top of the candle's range."""
    c = df.iloc[-1]
    body = abs(c["close"] - c["open"])
    lower_wick = min(c["close"], c["open"]) - c["low"]
    upper_wick = c["high"] - max(c["close"], c["open"])
    full_range = c["high"] - c["low"]
    if full_range == 0 or body == 0:
        return False
    return bool(lower_wick > body * wick_ratio and lower_wick > upper_wick * 1.5)


def is_bearish_pin_bar(df, wick_ratio=2.0):
    c = df.iloc[-1]
    body = abs(c["close"] - c["open"])
    lower_wick = min(c["close"], c["open"]) - c["low"]
    upper_wick = c["high"] - max(c["close"], c["open"])
    full_range = c["high"] - c["low"]
    if full_range == 0 or body == 0:
        return False
    return bool(upper_wick > body * wick_ratio and upper_wick > lower_wick * 1.5)


# =========================================================================
# TOP-DOWN SCAN
# =========================================================================

def scan_ticker(ticker):
    print(f"\n{'=' * 60}\n{ticker}\n{'=' * 60}")

    timeframes = {
        "Weekly": ("2y", "1wk"),
        "Daily": ("1y", "1d"),
        "4-Hour": ("60d", "1h"),   # yfinance has no native 4h; 1h is the finest free intraday
    }

    results = {}
    for label, (period, interval) in timeframes.items():
        df = fetch(ticker, period=period, interval=interval)
        if df is None or len(df) < 30:
            print(f"  [{label}] insufficient data")
            continue
        df = add_indicators(df)
        last = df.iloc[-1]
        fibs = fib_golden_pocket(df)

        trend = "BULLISH" if last["close"] > last["ema200"] else "BEARISH"
        rsi_state = (
            "OVERBOUGHT" if last["rsi14"] > 70
            else "OVERSOLD" if last["rsi14"] < 30
            else "NEUTRAL"
        )

        bull_engulf = is_bullish_engulfing(df)
        bear_engulf = is_bearish_engulfing(df)
        bull_pin = is_bullish_pin_bar(df)
        bear_pin = is_bearish_pin_bar(df)

        in_golden_pocket = fibs["golden_pocket_low"] <= last["close"] <= fibs["golden_pocket_high"]

        print(f"  [{label}] close={last['close']:.2f}  200ema={last['ema200']:.2f}  "
              f"trend={trend}  RSI={last['rsi14']:.1f} ({rsi_state})")
        if in_golden_pocket:
            print(f"    -> price is IN the 61.8% golden pocket "
                  f"({fibs['golden_pocket_low']:.2f}-{fibs['golden_pocket_high']:.2f})")
        if bull_engulf:
            print(f"    -> BULLISH ENGULFING candle detected")
        if bear_engulf:
            print(f"    -> BEARISH ENGULFING candle detected")
        if bull_pin:
            print(f"    -> BULLISH PIN BAR detected")
        if bear_pin:
            print(f"    -> BEARISH PIN BAR detected")

        results[label] = {
            "trend": trend, "rsi_state": rsi_state,
            "bull_signal": bull_engulf or bull_pin,
            "bear_signal": bear_engulf or bear_pin,
            "last_close": last["close"], "last_high": last["high"], "last_low": last["low"],
        }

    # Confluence check across timeframes
    if results:
        bull_count = sum(1 for r in results.values() if r["trend"] == "BULLISH")
        bull_signals = [tf for tf, r in results.items() if r["bull_signal"]]
        bear_signals = [tf for tf, r in results.items() if r["bear_signal"]]

        if bull_signals and bull_count >= 2:
            print(f"\n  *** CONFLUENCE ALERT: bullish pattern on {bull_signals} "
                  f"AND {bull_count}/{len(results)} timeframes trend bullish ***")
            last_daily = results.get("Daily")
            if last_daily:
                entry = round(last_daily["last_high"] + 0.15, 2)
                stop = round(last_daily["last_low"], 2)
                print(f"  15-cent rule entry (daily): {entry}  |  structural stop: {stop}  "
                      f"|  risk/share: {entry - stop:.2f}")
        if bear_signals and bull_count <= 1:
            print(f"\n  *** CONFLUENCE ALERT: bearish pattern on {bear_signals} "
                  f"with weak bullish trend alignment ***")

    return results


# =========================================================================
# POSITION / SCALE-OUT MANAGER
# =========================================================================

def check_positions():
    if not POSITIONS:
        return
    print(f"\n{'=' * 60}\nPOSITION CHECK\n{'=' * 60}")

    for ticker, pos in POSITIONS.items():
        df = fetch(ticker, period="6mo", interval="1d")
        if df is None:
            continue
        df = add_indicators(df)
        price = df.iloc[-1]["close"]

        entry, stop = pos["entry"], pos["stop"]
        risk_per_share = entry - stop
        if risk_per_share <= 0:
            print(f"  {ticker}: check config, stop is not below entry")
            continue

        current_r = (price - entry) / risk_per_share
        print(f"\n  {ticker}: price={price:.2f}  entry={entry:.2f}  stop={stop:.2f}  "
              f"current R={current_r:.2f}")

        # Stop-loss hit
        if price <= stop:
            print(f"    !!! STOP LOSS HIT -- structural level breached. Exit per plan. !!!")
            continue

        # Profit targets
        for target_r, fraction in pos.get("targets", []):
            if current_r >= target_r:
                shares_to_sell = round(pos["shares"] * fraction)
                print(f"    -> {target_r}R target reached: consider selling "
                      f"~{shares_to_sell} shares/contracts ({fraction*100:.0f}% of original size)")

        # Trailing stop guidance once past trail_after_R
        trail_after = pos.get("trail_after_R")
        if trail_after and current_r >= trail_after:
            method = pos.get("trail_method", "21ema")
            if method == "21ema":
                trail_level = df.iloc[-1]["ema21"]
            elif method == "8ema":
                trail_level = df.iloc[-1]["ema8"]
            else:  # swing_low over last 10 candles
                trail_level = df["low"].tail(10).min()
            print(f"    -> past {trail_after}R: trail remaining size below {method} "
                  f"= {trail_level:.2f} (raise your stop to this level)")


# =========================================================================
# MAIN
# =========================================================================

if __name__ == "__main__":
    print(f"Aristotle Alert System -- run at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    for t in WATCHLIST:
        try:
            scan_ticker(t)
        except Exception as e:
            print(f"  [{t}] error: {e}")

    check_positions()

    print(f"\n{'=' * 60}\nDone. Nothing here places trades -- confirm every signal yourself.\n{'=' * 60}")
