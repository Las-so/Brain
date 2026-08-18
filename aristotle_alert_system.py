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
pip install -r requirements.txt

Then either edit the WATCHLIST / POSITIONS defaults below, or (recommended)
copy config.example.json to config.json and edit that instead -- config.json
is gitignored so your real position sizes/entries never get committed. Run:

    python aristotle_alert_system.py --config config.json

For real daily use, wire this into a cron job / scheduled task so it runs
automatically (e.g. 8:00am and 3:30pm ET). Every run appends structured
output to a rotating log file (alerts.log by default) regardless of how
it's invoked, and can optionally push a summary of the important lines to a
Slack or Discord webhook via --webhook-url / ARISTOTLE_WEBHOOK_URL. See
README.md for cron/systemd examples.
"""

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger("aristotle")

# =========================================================================
# CONFIG -- defaults used when no --config file is supplied
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
    # Example -- replace with your real positions, or better: use config.json
    # "TSLA": {
    #     "entry": 250.00,
    #     "stop": 235.00,
    #     "shares": 30,
    #     "targets": [[1.0, 0.33], [2.0, 0.33]],
    #     "trail_after_R": 2.0,
    #     "trail_method": "21ema",   # "21ema", "8ema", or "swing_low"
    # },
}

FETCH_RETRIES = 3
FETCH_BACKOFF_SECONDS = 2

# =========================================================================
# DATA FETCHING
# =========================================================================

def fetch(ticker, period="1y", interval="1d", retries=FETCH_RETRIES, backoff=FETCH_BACKOFF_SECONDS):
    """Download OHLCV data with retries. Returns None (never raises) on
    persistent failure so one bad network call can't take down a whole run."""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        except Exception as exc:  # network hiccups, rate limits, bad symbols, etc.
            last_exc = exc
            df = None

        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                # yfinance can return MultiIndex columns (field, ticker) depending
                # on version/args; collapse to the field level we actually use.
                df.columns = df.columns.get_level_values(0)
            return df.rename(columns=str.lower)

        if attempt < retries:
            time.sleep(backoff ** attempt)

    if last_exc:
        logger.warning("fetch(%s, %s) failed after %d attempts: %s", ticker, interval, retries, last_exc)
    else:
        logger.warning("fetch(%s, %s) returned no data after %d attempts", ticker, interval, retries)
    return None


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
    result = 100 - (100 / (1 + rs))
    # avg_loss == 0 would otherwise divide to NaN and silently hide a strong
    # trend -- an all-up window is maximally overbought (100), an all-flat
    # window is conventionally neutral (50).
    result = result.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    result = result.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return result


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


def detect_divergence(df, indicator_col, lookback=20):
    """Simple divergence heuristic: does the most recent candle set a new
    price extreme that the indicator fails to confirm, versus the prior
    `lookback` candles? Returns "bullish", "bearish", or None.

    This is intentionally cheap (compares the latest candle to the single
    most extreme prior candle) rather than true swing-to-swing divergence --
    validate against your own chart reading before acting on it.
    """
    if len(df) < lookback + 1 or indicator_col not in df.columns:
        return None

    window = df.tail(lookback + 1)
    prior = window.iloc[:-1]
    last = window.iloc[-1]

    if prior[indicator_col].isna().any() or pd.isna(last[indicator_col]):
        return None

    prior_high_idx = prior["high"].idxmax()
    prior_low_idx = prior["low"].idxmin()

    bearish = bool(
        last["high"] > prior.loc[prior_high_idx, "high"]
        and last[indicator_col] < prior.loc[prior_high_idx, indicator_col]
    )
    bullish = bool(
        last["low"] < prior.loc[prior_low_idx, "low"]
        and last[indicator_col] > prior.loc[prior_low_idx, indicator_col]
    )

    if bearish:
        return "bearish"
    if bullish:
        return "bullish"
    return None


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

def scan_ticker(ticker, alerts=None):
    logger.info("\n%s\n%s\n%s", "=" * 60, ticker, "=" * 60)

    timeframes = {
        "Weekly": ("2y", "1wk"),
        "Daily": ("1y", "1d"),
        "4-Hour": ("60d", "1h"),   # yfinance has no native 4h; 1h is the finest free intraday
    }

    results = {}
    for label, (period, interval) in timeframes.items():
        try:
            df = fetch(ticker, period=period, interval=interval)
            if df is None or len(df) < 30:
                logger.info("  [%s] insufficient data", label)
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
            rsi_divergence = detect_divergence(df, "rsi14")
            macd_divergence = detect_divergence(df, "macd_hist")

            in_golden_pocket = fibs["golden_pocket_low"] <= last["close"] <= fibs["golden_pocket_high"]

            logger.info(
                "  [%s] close=%.2f  200ema=%.2f  trend=%s  RSI=%.1f (%s)",
                label, last["close"], last["ema200"], trend, last["rsi14"], rsi_state,
            )
            if in_golden_pocket:
                logger.info(
                    "    -> price is IN the 61.8%% golden pocket (%.2f-%.2f)",
                    fibs["golden_pocket_low"], fibs["golden_pocket_high"],
                )
            if bull_engulf:
                logger.info("    -> BULLISH ENGULFING candle detected")
            if bear_engulf:
                logger.info("    -> BEARISH ENGULFING candle detected")
            if bull_pin:
                logger.info("    -> BULLISH PIN BAR detected")
            if bear_pin:
                logger.info("    -> BEARISH PIN BAR detected")
            if rsi_divergence:
                logger.info("    -> %s RSI divergence detected", rsi_divergence.upper())
            if macd_divergence:
                logger.info("    -> %s MACD histogram divergence detected", macd_divergence.upper())

            results[label] = {
                "trend": trend, "rsi_state": rsi_state,
                "bull_signal": bull_engulf or bull_pin or rsi_divergence == "bullish" or macd_divergence == "bullish",
                "bear_signal": bear_engulf or bear_pin or rsi_divergence == "bearish" or macd_divergence == "bearish",
                "last_close": last["close"], "last_high": last["high"], "last_low": last["low"],
            }
        except Exception as exc:
            logger.error("  [%s] error scanning %s: %s", label, ticker, exc)

    # Confluence check across timeframes
    if results:
        bull_count = sum(1 for r in results.values() if r["trend"] == "BULLISH")
        bull_signals = [tf for tf, r in results.items() if r["bull_signal"]]
        bear_signals = [tf for tf, r in results.items() if r["bear_signal"]]

        if bull_signals and bull_count >= 2:
            msg = (
                f"*** CONFLUENCE ALERT: {ticker} bullish pattern on {bull_signals} "
                f"AND {bull_count}/{len(results)} timeframes trend bullish ***"
            )
            logger.info("\n  %s", msg)
            if alerts is not None:
                alerts.append(msg)
            last_daily = results.get("Daily")
            if last_daily:
                entry = round(last_daily["last_high"] + 0.15, 2)
                stop = round(last_daily["last_low"], 2)
                risk = entry - stop
                entry_msg = (
                    f"  {ticker} 15-cent rule entry (daily): {entry}  |  structural stop: {stop}  "
                    f"|  risk/share: {risk:.2f}"
                )
                logger.info(entry_msg)
                if alerts is not None:
                    alerts.append(entry_msg.strip())
        if bear_signals and bull_count <= 1:
            msg = (
                f"*** CONFLUENCE ALERT: {ticker} bearish pattern on {bear_signals} "
                f"with weak bullish trend alignment ***"
            )
            logger.info("\n  %s", msg)
            if alerts is not None:
                alerts.append(msg)

    return results


# =========================================================================
# POSITION / SCALE-OUT MANAGER
# =========================================================================

@dataclass
class PositionStatus:
    ticker: str
    price: float
    entry: float
    stop: float
    current_r: float
    stopped_out: bool
    targets_hit: list = field(default_factory=list)   # (target_r, fraction, shares_to_sell)
    trail_level: Optional[float] = None
    trail_method: Optional[str] = None


def evaluate_position(ticker, pos, price, ema8, ema21, swing_low_10):
    """Pure decision logic for a single position, kept separate from
    fetching/printing so it can be unit tested without network access."""
    entry, stop = pos["entry"], pos["stop"]
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        raise ValueError(f"{ticker}: stop ({stop}) must be below entry ({entry})")

    current_r = (price - entry) / risk_per_share
    stopped_out = price <= stop

    targets_hit = []
    if not stopped_out:
        for target_r, fraction in pos.get("targets", []):
            if current_r >= target_r:
                shares_to_sell = round(pos["shares"] * fraction)
                targets_hit.append((target_r, fraction, shares_to_sell))

    trail_level = None
    trail_method = pos.get("trail_method", "21ema")
    trail_after = pos.get("trail_after_R")
    if not stopped_out and trail_after and current_r >= trail_after:
        trail_level = {"21ema": ema21, "8ema": ema8}.get(trail_method, swing_low_10)

    return PositionStatus(
        ticker=ticker, price=price, entry=entry, stop=stop, current_r=current_r,
        stopped_out=stopped_out, targets_hit=targets_hit,
        trail_level=trail_level, trail_method=trail_method if trail_level is not None else None,
    )


def check_positions(positions, alerts=None):
    if not positions:
        return
    logger.info("\n%s\nPOSITION CHECK\n%s", "=" * 60, "=" * 60)

    for ticker, pos in positions.items():
        try:
            df = fetch(ticker, period="6mo", interval="1d")
            if df is None:
                logger.warning("  %s: could not fetch data, skipping position check", ticker)
                continue
            df = add_indicators(df)
            last = df.iloc[-1]
            swing_low_10 = df["low"].tail(10).min()

            status = evaluate_position(
                ticker, pos, last["close"], last["ema8"], last["ema21"], swing_low_10,
            )
        except ValueError as exc:
            logger.error("  %s: %s", ticker, exc)
            continue
        except Exception as exc:
            logger.error("  %s: error checking position: %s", ticker, exc)
            continue

        logger.info(
            "\n  %s: price=%.2f  entry=%.2f  stop=%.2f  current R=%.2f",
            status.ticker, status.price, status.entry, status.stop, status.current_r,
        )

        if status.stopped_out:
            msg = f"!!! {ticker} STOP LOSS HIT -- structural level breached. Exit per plan. !!!"
            logger.info("    %s", msg)
            if alerts is not None:
                alerts.append(msg)
            continue

        for target_r, fraction, shares_to_sell in status.targets_hit:
            msg = (
                f"{ticker}: {target_r}R target reached -- consider selling "
                f"~{shares_to_sell} shares/contracts ({fraction * 100:.0f}% of original size)"
            )
            logger.info("    -> %s", msg)
            if alerts is not None:
                alerts.append(msg)

        if status.trail_level is not None:
            msg = (
                f"{ticker}: past {pos.get('trail_after_R')}R -- trail remaining size below "
                f"{status.trail_method} = {status.trail_level:.2f} (raise your stop to this level)"
            )
            logger.info("    -> %s", msg)
            if alerts is not None:
                alerts.append(msg)


# =========================================================================
# CONFIG / NOTIFICATIONS
# =========================================================================

def load_config(path):
    """Load watchlist/positions from a JSON file if it exists, else fall
    back to the in-script defaults. See config.example.json."""
    if not path or not os.path.exists(path):
        return WATCHLIST, POSITIONS
    with open(path) as f:
        data = json.load(f)
    return data.get("watchlist", WATCHLIST), data.get("positions", POSITIONS)


def notify(message, webhook_url):
    """Best-effort push of a summary to a Slack or Discord incoming webhook.
    Never raises -- a notification failure should not fail the scan."""
    if not webhook_url or not message:
        return
    payload = {"content": message} if "discord.com" in webhook_url else {"text": message}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Webhook notification failed: %s", exc)


def setup_logging(log_file, quiet=False):
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    if not quiet:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console)

    if log_file:
        file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(file_handler)


# =========================================================================
# MAIN
# =========================================================================

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Aristotle Alert System")
    parser.add_argument(
        "--config", default=os.environ.get("ARISTOTLE_CONFIG", "config.json"),
        help="Path to a JSON file with 'watchlist' and 'positions' keys (default: config.json if present)",
    )
    parser.add_argument(
        "--log-file", default=os.environ.get("ARISTOTLE_LOG_FILE", "alerts.log"),
        help="Rotating log file path, or '' to disable file logging",
    )
    parser.add_argument(
        "--webhook-url", default=os.environ.get("ARISTOTLE_WEBHOOK_URL", ""),
        help="Slack or Discord incoming webhook URL for a summary of important alerts",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress console output (log file only)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    setup_logging(args.log_file, args.quiet)
    watchlist, positions = load_config(args.config)

    logger.info("Aristotle Alert System -- run at %s", datetime.now().strftime("%Y-%m-%d %H:%M"))

    important_alerts = []
    for t in watchlist:
        try:
            scan_ticker(t, important_alerts)
        except Exception as e:
            logger.error("  [%s] error: %s", t, e)

    check_positions(positions, important_alerts)

    logger.info(
        "\n%s\nDone. Nothing here places trades -- confirm every signal yourself.\n%s",
        "=" * 60, "=" * 60,
    )

    if important_alerts:
        notify("\n".join(important_alerts), args.webhook_url)


if __name__ == "__main__":
    main()
