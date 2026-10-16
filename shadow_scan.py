#!/usr/bin/env python3
"""Shadow-test scan: find candlestick-clone setups on YESTERDAY's completed daily
candle, check whether today's intraday action has triggered the 15c entry, and
print the paper-trade table. Nothing is placed anywhere."""
import pandas as pd
import yfinance as yf

UNIVERSE = [
    "SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "AMZN", "AMD", "META", "GOOGL",
    "MSFT", "PLTR", "SOFI", "NFLX", "DIS", "BA", "COP", "SLB", "UPS", "CRM",
    "NOW", "WDAY", "LYFT", "MARA", "RIOT", "COIN", "HOOD", "F", "INTC", "UBER",
    "NVTS", "QBTS", "APLD", "WULF", "XBIT", "REAL", "INDI", "IONQ", "SNAP", "PYPL",
    "ORCL", "AVGO", "MU", "SMCI", "DELL", "C", "BAC", "JPM", "WFC", "XOM", "CVX", "OXY", "T", "VZ", "PFE", "MRNA", "NKE", "SBUX", "TGT", "WMT", "GM", "RIVN", "LCID", "PLUG", "CHPT", "AAL", "CCL", "NCLH", "DKNG", "RBLX", "U", "SHOP", "SQ", "AFRM", "UPST", "CLF", "X", "AA", "FCX", "GDX", "TLT", "XLE", "XLF", "SMH", "ARKK", "BITO", "ETHA", "MSTR", "CLSK", "CIFR", "IREN", "CORZ", "BBAI", "SOUN", "LUNR", "RKLB", "ASTS", "NOK", "SIRI", "OPEN",
]
WICK = 2.0
LEVEL = 0.02

rows = []
for t in UNIVERSE:
    try:
        df = yf.Ticker(t).history(period="420d", interval="1d", auto_adjust=True)
    except Exception:
        continue
    if df is None or len(df) < 210:
        continue
    df = df.rename(columns=str.lower)
    # yesterday = last COMPLETED candle; if today's partial bar is present, drop it
    last_date = df.index[-1].date()
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).astimezone().date()
    intraday = None
    if last_date == pd.Timestamp("2026-10-16").date():
        intraday = df.iloc[-1]
        df = df.iloc[:-1]
    sig = df.iloc[-1]  # Thursday Oct 15 candle
    prev = df.iloc[-2]
    o, h, l, c = sig["open"], sig["high"], sig["low"], sig["close"]
    ma200 = df["close"].rolling(200).mean().iloc[-1]
    lo20 = df["low"].rolling(20).min().iloc[-2]
    hi20 = df["high"].rolling(20).max().iloc[-2]
    red_run = all(df["close"].iloc[-4 + k] < df["open"].iloc[-4 + k] for k in range(3))
    green_run = all(df["close"].iloc[-4 + k] > df["open"].iloc[-4 + k] for k in range(3))

    bt, bb = max(o, c), min(o, c)
    body = max(bt - bb, 1e-9)
    lw, uw = bb - l, h - bt
    bull_pin = lw >= WICK * body and lw > uw
    bear_pin = uw >= WICK * body and uw > lw
    bull_eng = (prev["close"] < prev["open"] and c > o and o <= prev["close"] and c >= prev["open"])
    bear_eng = (prev["close"] > prev["open"] and c < o and o >= prev["close"] and c <= prev["open"])
    har = (max(o, c) <= max(prev["open"], prev["close"]) and min(o, c) >= min(prev["open"], prev["close"]))

    near_sup = l <= lo20 * (1 + LEVEL) or (not pd.isna(ma200) and abs(l - ma200) / ma200 <= LEVEL)
    near_res = h >= hi20 * (1 - LEVEL) or (not pd.isna(ma200) and abs(h - ma200) / ma200 <= LEVEL)

    side = pattern = None
    if red_run and near_sup and (bull_pin or bull_eng):
        side, pattern = "BULL", "pin" if bull_pin else "engulf"
    elif green_run and near_res and (bear_pin or bear_eng):
        side, pattern = "BEAR", "pin" if bear_pin else "engulf"
    elif har and (red_run or green_run):
        side, pattern = ("BULL" if red_run else "BEAR"), "harami"
    if not side:
        continue

    entry = round(h + 0.15, 2) if side == "BULL" else round(l - 0.15, 2)
    stop = round(l, 2) if side == "BULL" else round(h, 2)
    trig = ""
    spot = ""
    if intraday is not None:
        spot = round(intraday["close"], 2)
        if side == "BULL":
            trig = "TRIGGERED" if intraday["high"] >= entry else "not yet"
        else:
            trig = "TRIGGERED" if intraday["low"] <= entry else "not yet"
    rows.append(dict(ticker=t, side=side, pattern=pattern, sig_date=str(df.index[-1].date()),
                     entry=entry, stop=stop, risk=round(abs(entry - stop), 2),
                     spot_now=spot, today=trig))

out = pd.DataFrame(rows)
if out.empty:
    print("NO valid setups on yesterday's candle across the 40-ticker universe.")
else:
    print(out.to_string(index=False))
