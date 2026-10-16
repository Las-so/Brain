# Shadow Test — Friday Oct 16, 2026 (PAPER ONLY, nothing placed)

Six positions, 3 bull / 3 bear, signals from Thursday Oct 15's completed daily candle.
All contracts 2026-11-13 expiry (28 DTE), quotes from Robinhood live at 15:47 UTC (10:47 AM CT).
Fill convention: paper entry at the ask when the underlying crosses the 15c trigger; paper exit at the bid.

| # | Ticker | Side | Pattern | Trigger (und.) | Stop (und.) | Contract | Bid/Ask @ morning | Mark | OI | Status @ 10:47 CT |
|---|--------|------|---------|----------------|-------------|----------|-------------------|------|----|--------------------|
| 1 | SLB | BULL | pin bar at support | 48.55 | 47.17 | 11/13 $49 C | 2.04 / 2.68 | 2.36 | 17 | TRIGGERED pre-10:47; paper-filled @ 2.68 |
| 2 | AAL | BULL | engulfing | 12.49 | 11.73 | 11/13 $12.5 C | 0.53 / 0.59 | 0.56 | 487 | waiting (spot 12.27) |
| 3 | SOUN | BULL | engulfing | 5.05 | 4.39 | 11/13 $5 C | 0.28 / 0.38 | 0.33 | 483 | waiting (spot 4.83) |
| 4 | COP | BEAR | engulfing (RSI 80+) | 140.66 | 143.13 | 11/13 $140 P | 2.68 / 3.35 | 3.02 | 60 | waiting (spot ~144.2) |
| 5 | XOM | BEAR | engulfing | 173.45 | 178.69 | 11/13 $172.5 P | 3.70 / 4.00 | 3.85 | 728 | waiting (spot ~176.0) |
| 6 | XLE | BEAR | engulfing | 66.02 | 67.90 | 11/13 $66 P | 1.21 / 1.28 | 1.25 | 102 | waiting (spot ~67.4) |

Flags at open of test:
- SLB: triggered before this scan started, so its paper fill at the 10:47 ask (2.68) is LATE relative to the true trigger moment; the real fill would likely have been cheaper. Earnings Oct 23 is INSIDE the holding window. Larry's main account also holds SLB with a live stop at 46.14; this paper long agrees with his book.
- COP: his main account holds COP (RSI 82.9, most-extended name after LYFT). A triggered COP put would hedge his own long. Premium $302 at mark exceeds the $50-100 live cap; allowed in paper, would be rejected live.
- XOM/COP/XLE are one energy factor bet, same as his AI-datacenter correlation lesson. Three bear triggers = one macro short on energy, not three trades.
- SLB bull + XLE/XOM/COP bear is internally contradictory (SLB is energy services). If both sides trigger the strategy is churning one sector's chop.
- IONQ and MSTR setups excluded: risk/share too wide for any premium discipline.
- Dropped XOM would cost $385-400 premium; also over the live cap. Only AAL, SOUN, XLE and roughly SLB fit the real $50-100 premium band.

## Checkpoint log
- 10:47 CT (morning): table above. 1 of 6 triggered (SLB).
