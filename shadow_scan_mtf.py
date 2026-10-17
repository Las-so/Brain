#!/usr/bin/env python3
"""Shadow scan v2: daily candlestick signal + multi-timeframe confluence (4H and 30m),
sector-capped (max 2 per sector), returns top setups. Watch-only; nothing placed."""
import datetime
import pandas as pd
import yfinance as yf

SECTORS = {
    "tech": ["NVDA", "AAPL", "MSFT", "AMD", "META", "GOOGL", "AMZN", "ORCL", "AVGO", "MU", "DELL", "INTC", "SMCI", "PLTR", "CRM", "NOW", "WDAY", "SHOP", "U", "RBLX", "SNAP", "SOUN", "BBAI", "IONQ", "QBTS"],
    "energy": ["XOM", "CVX", "COP", "SLB", "OXY", "XLE", "USO"],
    "financial": ["JPM", "BAC", "C", "WFC", "XLF", "SOFI", "HOOD", "COIN", "PYPL", "AFRM", "UPST"],
    "healthcare": ["JNJ", "UNH", "LLY", "ABBV", "MRK", "BMY", "PFE", "MRNA", "CVS", "XLV"],
    "industrial": ["CAT", "DE", "HON", "GE", "UNP", "FDX", "UPS", "BA", "MMM", "XLI"],
    "consumer": ["WMT", "TGT", "COST", "HD", "LOW", "MCD", "SBUX", "NKE", "KO", "PEP", "PG", "DIS", "XLY", "XLP"],
    "transport_travel": ["AAL", "DAL", "UAL", "LUV", "CCL", "NCLH", "ABNB", "UBER", "LYFT", "GM", "F", "RIVN"],
    "materials_metals": ["FCX", "CLF", "AA", "GDX", "GLD", "SLV", "XLB"],
    "crypto_adjacent": ["MSTR", "MARA", "RIOT", "CLSK", "BITO", "ETHA"],
    "utilities_reits": ["NEE", "DUK", "O", "AMT", "XLU"],
    "media_telecom": ["T", "VZ", "NFLX", "SIRI", "ROKU", "PINS", "DKNG"],
    "space_defense": ["RKLB", "LUNR", "ASTS"],
}
from universe_industries import TICKER_SECTOR, UNIVERSE  # noqa: E402 — 60+ industry groups, ~240 names
WICK, LEVEL = 2.0, 0.02


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def trend(df):
    """'bull'/'bear'/'flat' from 8/21 EMA + price vs 21."""
    if df is None or len(df) < 25:
        return "n/a"
    c = df["close"]
    e8, e21 = ema(c, 8).iloc[-1], ema(c, 21).iloc[-1]
    px = c.iloc[-1]
    if e8 > e21 and px > e21:
        return "bull"
    if e8 < e21 and px < e21:
        return "bear"
    return "flat"


daily_cache = {}
rows = []
for t in UNIVERSE:
    try:
        df = yf.Ticker(t).history(period="420d", interval="1d", auto_adjust=True)
    except Exception:
        continue
    if df is None or len(df) < 210:
        continue
    df = df.rename(columns=str.lower)
    intraday = None
    if df.index[-1].date() == datetime.date(2026, 10, 16):
        intraday = df.iloc[-1]
        df = df.iloc[:-1]
    sig, prev = df.iloc[-1], df.iloc[-2]
    o, h, l, c = sig["open"], sig["high"], sig["low"], sig["close"]
    ma200 = df["close"].rolling(200).mean().iloc[-1]
    lo20, hi20 = df["low"].rolling(20).min().iloc[-2], df["high"].rolling(20).max().iloc[-2]
    red_run = all(df["close"].iloc[-4 + k] < df["open"].iloc[-4 + k] for k in range(3))
    green_run = all(df["close"].iloc[-4 + k] > df["open"].iloc[-4 + k] for k in range(3))
    bt, bb = max(o, c), min(o, c)
    body = max(bt - bb, 1e-9)
    lw, uw = bb - l, h - bt
    bull_pin = lw >= WICK * body and lw > uw
    bear_pin = uw >= WICK * body and uw > lw
    bull_eng = prev["close"] < prev["open"] and c > o and o <= prev["close"] and c >= prev["open"]
    bear_eng = prev["close"] > prev["open"] and c < o and o >= prev["close"] and c <= prev["open"]
    har = bt <= max(prev["open"], prev["close"]) and bb >= min(prev["open"], prev["close"])
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

    # multi-timeframe confluence: 4H (from 1h bars) and 30m
    try:
        h1 = yf.Ticker(t).history(period="30d", interval="1h", auto_adjust=True).rename(columns=str.lower)
        h4 = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        m30 = yf.Ticker(t).history(period="10d", interval="30m", auto_adjust=True).rename(columns=str.lower)
    except Exception:
        h4, m30 = None, None
    t4, t30 = trend(h4), trend(m30)
    want = "bull" if side == "BULL" else "bear"
    # Reversal logic: daily signal fires INTO a counter-trend, so 4H still showing the old
    # trend is normal. Confluence = the LOWER timeframe (30m) turning in the signal's
    # direction = the turn is underway. Score: 2 = 30m aligned and 4H aligned-or-flat,
    # 1 = 30m aligned only, 0 = 30m not aligned.
    score = 0
    if t30 == want:
        score = 2 if t4 in (want, "flat") else 1
    entry = round(h + 0.15, 2) if side == "BULL" else round(l - 0.15, 2)
    stop = round(l, 2) if side == "BULL" else round(h, 2)
    trig, spot = "", ""
    if intraday is not None:
        spot = round(intraday["close"], 2)
        hit = intraday["high"] >= entry if side == "BULL" else intraday["low"] <= entry
        trig = "TRIGGERED" if hit else "not yet"
    rows.append(dict(ticker=t, sector=TICKER_SECTOR[t], side=side, pattern=pattern,
                     entry=entry, stop=stop, spot=spot, trig_today=trig,
                     tf_4h=t4, tf_30m=t30, mtf_score=score))

out = pd.DataFrame(rows).sort_values(["mtf_score"], ascending=False)
print("ALL candidates (daily signal from Thu Oct 15):")
print(out.to_string(index=False))

# sector cap: max 2 per sector, prefer higher mtf score, aim for 9
picked, count = [], {}
for _, r in out.iterrows():
    if count.get(r["sector"], 0) >= 2:
        continue
    picked.append(r)
    count[r["sector"]] = count.get(r["sector"], 0) + 1
    if len(picked) >= 9:
        break
print(f"\nPICKED {len(picked)} (sector-capped, MTF-ranked):")
print(pd.DataFrame(picked).to_string(index=False))
