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

### 12:01 PM CT midday checkpoint (fresh scan + fresh Robinhood quotes 17:01 UTC)
- SLB (MTF 2, the A-grade setup): spot 49.64, further above the 48.55 entry. $49C mark 2.645
  vs 2.68 paper fill at 10:47 = roughly flat (-$3/contract at mark, bid 2.47 if sold). The
  stock is +1.09 past entry, so a true fill at the trigger moment would be well green; our
  10:47 late-fill convention eats that.
- UAL: triggered at 101.78 this morning, now 98.39, BELOW the 98.13 stop level territory
  (stop 98.13, spot 0.26 above it). A paper long from the trigger is near max loss. The
  intraday failed-break lesson in full.
- AAL: faded to 12.09, never triggered. The waiting rule saved the premium.
- SOUN 4.72, IONQ 31.87, MSTR 137.37: none triggered, all MTF 0.
- Bears COP (145.79) / XOM (177.32) / XLE (67.86): none triggered, moving AWAY from their
  triggers all day; XLE is 4 cents from its 67.90 stop level on the signal candle. Energy is
  rallying, the bear engulfs are failing without ever confirming. The 15c rule filtered all
  three, exactly its job.
- Midday read: entry-confirmation + MTF is doing the work. The only filled name is the only
  MTF-2 name and the only one above water on the underlying; every skipped trigger saved money.

### 2:47 PM CT NEAR-CLOSE FINAL (fresh scan + Robinhood quotes 19:47 UTC)
Day's scoreboard, all 9, watch-only:
- SLB (BULL, MTF 2): the day's only win. Spot 49.55, held $1.00 above entry all afternoon.
  $49C mark 2.44 at close vs morning quotes; our LATE 10:47 paper fill at 2.68 shows -$24,
  but SLB crossed 48.55 around the open when the contract was near its 1.87 prior close —
  a true at-trigger fill would be up roughly $55-57/contract (+~30%). Logged both numbers.
- UAL (BULL, MTF 0): triggered 101.78, closed near 96.29 — through the 98.13 stop. Paper
  loss at stop = -1R on the underlying; the option would have lost roughly half its premium.
  The day's only stop-out, and it was the MTF-0 trigger.
- AAL (MTF 1 morning, decayed to 0): never triggered, faded to 11.87. Premium saved.
- SOUN, IONQ, MSTR (MTF 0): never triggered. Premium saved.
- COP, XOM, XLE (BEAR, MTF 0): never triggered; energy rallied all day (XOM closed 4 cents
  from invalidating its signal candle). All three bear engulfs failed WITHOUT costing money
  because the 15c break never came. COP $140P mark fell 4.45 -> 2.72 (-39%) — that is what
  buying the unconfirmed bear thesis at yesterday's close would have lost.

DAY'S LEDGER (would-have-been): 1 winner (SLB, the only MTF-2), 1 stop-out (UAL, MTF-0),
7 no-trades that cost nothing. Net on the two fills at true-trigger pricing: roughly +$55
on SLB vs -$30 to -$50 on UAL depending on exit discipline — approximately breakeven to
slightly positive, with the entire difference carried by the MTF filter.
