# Shadow Test — Friday Oct 16, 2026 (WATCH ONLY, nothing placed anywhere)

Nine positions, every valid setup from Thursday Oct 15's completed daily candle across a
95-ticker, 12-sector universe. Multi-timeframe check per the Aristotle top-down framework:
daily signal, 4H trend, 30m trend (8/21 EMA structure). A reversal signal normally fires
against the 4H trend, so confluence = the 30m turning in the signal's direction.
MTF score: 2 = 30m aligned and 4H aligned or flat; 1 = 30m aligned; 0 = 30m not turned yet.

| # | Ticker | Sector | Side | Pattern | Entry trig | Stop | 4H | 30m | MTF | Status @ 11:10 CT |
|---|--------|--------|------|---------|-----------|------|----|-----|-----|--------------------|
| 1 | SLB | energy | BULL | pin at support | 48.55 | 47.17 | flat | bull | 2 | TRIGGERED (spot 49.32) |
| 2 | AAL | travel | BULL | engulf | 12.49 | 11.73 | bear | bull | 1 | waiting (12.22) |
| 3 | UAL | travel | BULL | engulf | 101.78 | 98.13 | bear | flat | 0 | TRIGGERED (99.75, back below entry) |
| 4 | SOUN | tech | BULL | engulf | 5.05 | 4.39 | bear | flat | 0 | waiting (4.72) |
| 5 | IONQ | tech | BULL | engulf | 34.51 | 30.03 | bear | bear | 0 | waiting (32.01) |
| 6 | MSTR | crypto | BULL | engulf | 151.48 | 134.89 | bear | bear | 0 | waiting (137.58) |
| 7 | COP | energy | BEAR | engulf | 140.66 | 143.13 | bull | bull | 0 | waiting (144.55) |
| 8 | XOM | energy | BEAR | engulf | 173.45 | 178.69 | bull | bull | 0 | waiting (176.24) |
| 9 | XLE | energy | BEAR | engulf | 66.02 | 67.90 | bull | bull | 0 | waiting (67.42) |

Reference option contracts (all 11/13 expiry, 28 DTE, Robinhood quotes 15:47 UTC) for the
original six: SLB $49C 2.04/2.68, AAL $12.5C 0.53/0.59, SOUN $5C 0.28/0.38,
COP $140P 2.68/3.35, XOM $172.5P 3.70/4.00, XLE $66P 1.21/1.28.

Standing flags:
- SECTOR CONCENTRATION IS THE MARKET'S DOING: the scan covered 12 sectors and these nine
  are everything that qualified. Energy printed 4 of 9. The three energy bears are ONE macro
  short; SLB bull contradicts them. Max 2 energy count toward any live recommendation.
- MTF scores are brutal on the bears: COP/XOM/XLE show bull on BOTH lower timeframes, so
  their daily bear engulfs have no lower-timeframe confirmation yet. Only SLB (2) and
  AAL (1) have the 30m turned.
- UAL triggered at 101.78 then fell back under entry; that is what a failed break looks like
  intraday and is exactly what the 15c rule is supposed to filter on the daily close.
- SLB earnings Oct 23 inside the holding window; main account holds SLB (live stop 46.14) and COP.
- COP ($335) and XOM ($385+) premiums exceed the live $50-100 cap; watch-only here, would be
  rejected live.
- IONQ/MSTR risk-per-share very wide (4.48 / 16.59); included to watch, questionable live.

## Checkpoint log
- 10:47 CT (morning, v1, six names, daily-only scan): SLB triggered; logged in git history.
- 11:10 CT (morning v2, nine names, MTF + sector check added at Larry's correction): table above.
  2 of 9 triggered (SLB holding above entry, UAL failed back below).
