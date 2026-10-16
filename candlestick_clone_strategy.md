# Candlestick Clone Strategy — The Trading Bondsman

Cloned 2026-10-16 from the candlestick course video (same lineage as the Aristotle framework).
This file is the reusable context. The detection engine is `aristotle_alert_system.py`; the
backtest harness is `candlestick_backtest.py`.

## The three patterns (daily chart)

1. **Pin bar** (the number one pattern). Long wick rejecting one direction, small body near the
   opposite end. Bullish: appears after a run of red candles, pinned AT a form of support
   (horizontal level, break-and-retest, pullback zone, 200 MA). Bearish: mirror image after a
   run of green candles at resistance. Not a pin bar if it is not at a level. Not a hammer or
   shooting star: the close does not have to be at the extreme.
2. **Engulfing.** Today's BODY fully engulfs yesterday's BODY (open and close both beyond
   yesterday's). Wicks do not matter. Needs a prior trend to eat. Engulfing at the 200-day MA,
   Fibonacci, or a support line is the highest-probability version.
3. **Harami / inside bar.** Today smaller than and inside yesterday. Lower probability. Entry
   range is the mother candle's full high/low INCLUDING wicks; enter on a break of that range.

## Execution rules

- **Entry:** 15 cents above the signal candle high (long) or 15 cents below the low (short).
  10 cents acceptable on cheap names. No break, no trade: the break is the confirmation.
- **Stop:** the opposite extreme of the signal candle. Stay in while the stop is not hit.
- **Trigger window:** if the break does not come within 3 sessions, the setup is dead.
- **First trim:** 2R on the underlying.

## Larry's standing trade plan (decided 2026-10-16)

- Account: the MCP account 726952948 only (agentic, option level 3).
- Instrument: options. Calls on bullish setups, puts on bearish. Both directions.
- Contract: 14-30 DTE, at the money or one step out, tight bid/ask, real open interest.
  No weeklies.
- Risk: $50 max loss per trade. Premium cap roughly $50-100 because an underlying-based stop
  typically burns 40-70% of the premium.
- No entries on names with earnings before expiration unless loudly flagged.
- Execution: Claude sends the exact order spec; Larry replies GO; only then is the order
  placed. Per-order authorization, never standing.

## Status

Edge UNVERIFIED until the backtest and the live trade log say otherwise. Run
`python candlestick_backtest.py` for the current numbers.
