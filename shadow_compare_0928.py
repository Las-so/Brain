#!/usr/bin/env python3
"""15c vs 9c trigger shadow comparison for Oct 28's 12 setups. Read-only."""
import yfinance as yf

# ticker: (side, entry15, stop)
SETUPS = {
    "ABT": ("bear", 101.76, 104.28), "GOOGL": ("bull", 324.03, 316.86),
    "BX": ("bear", 116.40, 120.55), "TFC": ("bear", 48.37, 49.27),
    "CF": ("bear", 119.69, 122.36), "ZS": ("bear", 255.17, 267.87),
    "COIN": ("bull", 162.02, 157.75), "LNG": ("bear", 297.41, 304.73),
    "LMT": ("bear", 622.55, 633.56), "GD": ("bear", 353.85, 357.46),
    "REAL": ("bear", 10.56, 11.25), "APP": ("bull", 264.20, 257.50),
}

print(f"{'tkr':>6} {'side':>4} {'15c trig':>9} {'9c trig':>8} {'day lo':>8} {'day hi':>8} {'close':>8}  15c | 9c outcome")
for t, (side, e15, stop) in SETUPS.items():
    df = yf.Ticker(t).history(period="1d", interval="5m")
    if df is None or len(df) == 0:
        print(f"{t:>6}  NO DATA")
        continue
    lo, hi, close = df["Low"].min(), df["High"].max(), df["Close"].iloc[-1]
    e9 = round(e15 + 0.06, 2) if side == "bear" else round(e15 - 0.06, 2)

    def outcome(entry):
        if side == "bear":
            fired = lo <= entry
            if not fired:
                return "no fire"
            stopped = hi >= stop  # crude: any touch of stop after is approximated by day high
            mtm = (entry - close)  # per-share move in favor since entry
            return f"FIRED{' STOPPED' if stopped else ''}, close {'+' if mtm>=0 else ''}{mtm:.2f}/sh"
        fired = hi >= entry
        if not fired:
            return "no fire"
        stopped = lo <= stop
        mtm = (close - entry)
        return f"FIRED{' STOPPED' if stopped else ''}, close {'+' if mtm>=0 else ''}{mtm:.2f}/sh"

    print(f"{t:>6} {side:>4} {e15:>9.2f} {e9:>8.2f} {lo:>8.2f} {hi:>8.2f} {close:>8.2f}  {outcome(e15)} | {outcome(e9)}")
