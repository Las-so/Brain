# Shadow Test — Wed Oct 28, 2026: 15-cent vs 9-cent trigger, plus the first live order

Larry's order: live rule stays 15 cents; shadow a 9-cent trigger across the day's 12 setups
(signal = Mon Oct 27 daily candle). Data: 5m intraday bars at 2:56 PM CT.

## Side-by-side (bears: 9c trigger sits 6c ABOVE the 15c one; bulls: 6c below)

| Ticker | Side | 15c trig | 9c trig | Day lo | Day hi | Close | 15c outcome | 9c outcome |
|---|---|---|---|---|---|---|---|---|
| ABT | bear | 101.76 | 101.82 | 101.54 | 103.93 | 102.90 | fired, -1.14/sh at close | fired, -1.08/sh |
| GOOGL | bull | 324.03 | 323.97 | 322.65 | 326.40 | 324.97 | fired, +0.94/sh | fired, +1.00/sh |
| BX | bear | 116.40 | 116.46 | 116.14 | 118.61 | 117.10 | fired, -0.70/sh | fired, -0.64/sh |
| TFC | bear | 48.37 | 48.43 | 48.12 | 48.86 | 48.47 | fired, -0.10/sh | fired, -0.04/sh |
| CF | bear | 119.69 | 119.75 | 118.61 | 120.46 | 119.79 | fired, -0.10/sh | fired, -0.04/sh |
| ZS | bear | 255.17 | 255.23 | 254.29 | 265.99 | 255.59 | fired, -0.42/sh | fired, -0.36/sh |
| COIN | bull | 162.02 | 161.96 | 156.64 | 162.05 | 161.93 | fired, STOPPED | fired, STOPPED |
| LNG | bear | 297.41 | 297.47 | 296.53 | 302.00 | 297.13 | fired, +0.28/sh | fired, +0.34/sh |
| LMT | bear | 622.55 | 622.61 | 614.00 | 635.96 | 631.57 | fired, STOPPED -9.02/sh | fired, STOPPED |
| GD | bear | 353.85 | 353.91 | 352.14 | 355.65 | 354.58 | fired, -0.73/sh | fired, -0.67/sh |
| REAL | bear | 10.56 | 10.62 | 10.87 | 11.23 | 11.10 | no fire | no fire |
| APP | bull | 264.20 | 264.14 | 257.10 | 262.79 | 259.98 | no fire | no fire |

(Outcome = per-share mark vs entry at ~2:56 PM CT; STOPPED = the stop level traded after entry.
Crude on sequencing: stop-vs-close ordering approximated from day extremes.)

## VERDICT ON 9 CENTS, today's evidence
- The two triggers took THE SAME trades: 10 of 12 fired under both, the same 2 never fired.
  Not one setup fired at 9c and stayed clean at 15c by day's end.
- Where both fired, 9c was exactly 6 cents/share better on entry price, by construction.
- The intraday difference DID appear once: at 9:18 AM, TFC's 9c trigger had fired into a
  bounce (a fakeout position) while the 15c trigger was still clean. By the close the 15c
  fired too, so the day erased the distinction, but the morning snapshot shows the cost of
  the thinner buffer: it gets you into fakeouts sooner.
- Day character: a chop/fakeout day. 10 fired triggers produced 2 stop-outs (COIN, LMT —
  LMT -$9/sh), 6 closes against entry, 2 small wins. A day where taking fewer trades won.
- RECOMMENDATION: keep 15c. The 9c trigger's only measurable edge today was 6 cents of
  entry price; its measurable cost is earlier entry into fakeouts on a day made of them.

## THE LIVE TFC ORDER — final status
- 9:47 AM CT: GO executed, BUY 1x 11/20 $47.50 put, 0.90 limit GFD (order 6ae20af0). Placed
  AFTER the break (polling lag) — the put had already run to ~1.00+ and the 0.90 never filled.
- 12:07 PM CT: CANCELLED at Larry's word after the midday rescan showed TFC reclaiming the
  trigger. 0 filled, $0 spent, account intact at $221.88.
- Honest postscript: TFC later broke 48.37 again (day low 48.12) and closed 48.47 — a filled
  bear entry would have been roughly flat (-$4 to -$10 on the contract at the close, intraday
  swing both ways). The cancel neither cost nor saved much; the LESSON of the day is the
  entry mechanism, now fixed: resting STOP_LIMIT buy placed at GO time (saved in project
  preferences), earnings checked on ALL candidates, and no chasing a passed price.
