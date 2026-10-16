#!/usr/bin/env python3
"""Backtest v2: same candlestick rules, now scored by multi-timeframe confluence.

At each daily signal, compute the 4H trend and the 1H trend (8/21 EMA structure) as of
that signal's close, from hourly bars. 1H stands in for the 30m lower timeframe because
30m history only reaches ~60 days. Window ~2 years (the 1h data limit).

Reversal confluence (same rule as shadow_scan_mtf.py): the lower TF turning in the
signal's direction = the turn is underway. score 2 = 1H aligned AND 4H aligned-or-flat;
score 1 = 1H aligned; score 0 = 1H not aligned.
Outcome per trade unchanged: entry 15c break within 3 sessions, stop at candle extreme,
win = 2R first, 30-session time exit.
"""
import sys
import pandas as pd
import yfinance as yf

UNIVERSE = [
    "SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "AMZN", "AMD", "META", "GOOGL",
    "MSFT", "PLTR", "SOFI", "NFLX", "DIS", "BA", "COP", "SLB", "UPS", "CRM",
    "NOW", "WDAY", "LYFT", "MARA", "RIOT", "COIN", "HOOD", "F", "INTC", "UBER",
]
WICK, LEVEL, TRIG_WIN, MAX_HOLD, TICK = 2.0, 0.02, 3, 30, 0.15


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def trend_at(df_tf, ts):
    """Trend ('bull'/'bear'/'flat') on a timeframe as of timestamp ts."""
    sub = df_tf[df_tf.index <= ts]
    if len(sub) < 25:
        return "n/a"
    c = sub["close"]
    e8, e21, px = ema(c, 8).iloc[-1], ema(c, 21).iloc[-1], c.iloc[-1]
    if e8 > e21 and px > e21:
        return "bull"
    if e8 < e21 and px < e21:
        return "bear"
    return "flat"


trades = []
for ticker in UNIVERSE:
    try:
        d = yf.Ticker(ticker).history(period="729d", interval="1d", auto_adjust=True)
        h1 = yf.Ticker(ticker).history(period="729d", interval="1h", auto_adjust=True)
    except Exception as e:  # noqa: BLE001
        print(f"{ticker}: download failed ({e})", file=sys.stderr)
        continue
    if d is None or h1 is None or len(d) < 260 or len(h1) < 200:
        print(f"{ticker}: insufficient data", file=sys.stderr)
        continue
    d = d.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
    h1 = h1.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
    h4 = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    o, h, l, c = d["open"].values, d["high"].values, d["low"].values, d["close"].values
    ma200 = d["close"].rolling(200).mean().values
    lo20 = d["low"].rolling(20).min().values
    hi20 = d["high"].rolling(20).max().values

    for i in range(205, len(d) - 1):
        red = all(c[j] < o[j] for j in range(i - 3, i))
        green = all(c[j] > o[j] for j in range(i - 3, i))
        be_ = c[i - 1] < o[i - 1] and c[i] > o[i] and o[i] <= c[i - 1] and c[i] >= o[i - 1]
        se_ = c[i - 1] > o[i - 1] and c[i] < o[i] and o[i] >= c[i - 1] and c[i] <= o[i - 1]
        bt, bb = max(o[i], c[i]), min(o[i], c[i])
        body = max(bt - bb, 1e-9)
        lw, uw = bb - l[i], h[i] - bt
        bp = lw >= WICK * body and lw > uw
        sp = uw >= WICK * body and uw > lw
        near_sup = l[i] <= lo20[i - 1] * (1 + LEVEL) or (not pd.isna(ma200[i]) and abs(l[i] - ma200[i]) / ma200[i] <= LEVEL)
        near_res = h[i] >= hi20[i - 1] * (1 - LEVEL) or (not pd.isna(ma200[i]) and abs(h[i] - ma200[i]) / ma200[i] <= LEVEL)

        side = None
        if red and near_sup and (bp or be_):
            side, pattern = "long", "pin" if bp else "engulf"
        elif green and near_res and (sp or se_):
            side, pattern = "short", "pin" if sp else "engulf"
        if not side:
            continue

        ts = d.index[i] + pd.Timedelta(hours=23)  # end of signal day
        t4, t1 = trend_at(h4, ts), trend_at(h1, ts)
        want = "bull" if side == "long" else "bear"
        score = 0
        if t1 == want:
            score = 2 if t4 in (want, "flat") else 1

        entry = h[i] + TICK if side == "long" else l[i] - TICK
        stop = l[i] if side == "long" else h[i]
        risk = abs(entry - stop)
        if risk <= 0.01:
            continue
        target = entry + 2 * risk if side == "long" else entry - 2 * risk
        t = None
        for j in range(i + 1, min(i + 1 + TRIG_WIN, len(d))):
            if (side == "long" and h[j] >= entry) or (side == "short" and l[j] <= entry):
                t = j
                break
        if t is None:
            continue
        r_mult = None
        for j in range(t, min(t + MAX_HOLD, len(d))):
            stop_hit = l[j] <= stop if side == "long" else h[j] >= stop
            tgt_hit = h[j] >= target if side == "long" else l[j] <= target
            if stop_hit:
                r_mult = -1.0
                break
            if tgt_hit:
                r_mult = 2.0
                break
        if r_mult is None:
            j = min(t + MAX_HOLD, len(d)) - 1
            r_mult = ((c[j] - entry) / risk) if side == "long" else ((entry - c[j]) / risk)
        trades.append(dict(ticker=ticker, date=str(d.index[i].date()), side=side,
                           pattern=pattern, score=score, R=round(r_mult, 2)))

df = pd.DataFrame(trades)
if df.empty:
    print("No trades.")
    sys.exit()
df.to_csv("candlestick_backtest_mtf_results.csv", index=False)
print(f"Trades: {len(df)}  (2y window, 30 tickers, MTF-scored)\n")


def line(name, g):
    if len(g) == 0:
        print(f"  {name:>22}: n=   0")
        return
    wins = (g["R"] >= 2).sum()
    print(f"  {name:>22}: n={len(g):4d}  2R-win={wins/len(g):5.1%}  avg R={g['R'].mean():+.2f}  total R={g['R'].sum():+.1f}")


line("ALL", df)
for s in (0, 1, 2):
    line(f"score {s}", df[df.score == s])
line("score>=1 (MTF filter)", df[df.score >= 1])
print()
for side in ("long", "short"):
    for s in ("all", 0, 1, 2):
        g = df[df.side == side] if s == "all" else df[(df.side == side) & (df.score == s)]
        line(f"{side} score {s}", g)
