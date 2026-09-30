---
name: trade-desk
description: Research, screen, and log trades using Larry's two house frameworks — Stock Sundays (swing/reactive equity trades on SPY/QQQ/IWM and similar) and Trading Bondsman (LEAPS/options screening). Pulls live quotes, positions, historicals, and option chains via the RobinHood connector, runs the trade through the right framework's checklist, and outputs a full report. Every report gets saved as a file, a copy pushed to Google Drive, and filed into a grouped folder structure so it becomes a running trade journal. Use this skill any time Larry mentions a ticker + wanting to trade/research/screen it, LEAPS, options, neckline breaks, the 15-Cent Rule, Stock Sundays, Trading Bondsman, a trade journal/log entry, or asks "should I take this trade" / "pull up [ticker]" / "screen this for me" — even if he doesn't say the framework name explicitly.
---

# Trade Desk

Turns a ticker (or a batch of tickers) into a full trade report: live data pulled from RobinHood, run through the right house framework, saved as a file, copied to Drive, and filed into the trade log.

## Step 0 — Load tools

Both are deferred tools — call `tool_search` before using them if not already loaded:
- `tool_search(query="robinhood quotes positions")` → RobinHood tools
- `tool_search(query="google drive create file")` → Google Drive tools

## Step 1 — Figure out the trade type

Ask yourself (don't ask Larry unless genuinely ambiguous):
- **Swing / reactive equity trade** (stock, index ETF, short-to-medium hold, chart-based entry) → **Stock Sundays** framework. Read `references/stock-sundays.md`.
- **LEAPS / options position** (long-dated calls/puts, screening a list, profitability-driven) → **Trading Bondsman** framework. Read `references/trading-bondsman.md`.
- If genuinely both apply (e.g., he wants a LEAPS play on a name he's also charting for a swing entry), run both checklists in the same report, clearly separated.

## Step 2 — Pull live data (RobinHood)

At minimum:
- `get_equity_quotes` — current price, day range, volume
- `get_equity_historicals` — weekly + daily bars (Stock Sundays needs the top-down weekly → daily → 5-min read; pull what timeframes the tool supports and note any gap)
- `get_equity_fundamentals` — for context (market cap, sector, etc.)

For LEAPS/options trades, also pull:
- `get_option_chains` / `get_option_instruments` — find the relevant expirations/strikes
- `get_option_quotes` — live premium, bid/ask, IV
- `get_earnings_results` / `get_earnings_calendar` — earnings risk is a real input to LEAPS profitability

If Larry already has a position on the name, pull `get_equity_positions` or `get_option_positions` too and fold current P&L into the report.

Never place, review, or modify an order (`place_equity_order`, `place_option_order`, etc.) unless Larry explicitly asks you to — this skill is for research/screening/journaling, not execution.

## Step 3 — Run the checklist

Follow the relevant reference file's checklist structure exactly — don't freelance the methodology. Fill in real numbers from Step 2, not placeholders. If a data point isn't available from RobinHood, say so plainly in the report rather than guessing.

## Step 4 — Build the report

Use `references/report-template.md` as the structure. Fill it out completely — this is a "full checklist/report" by default, not a quick summary. Write it as a markdown file.

## Step 5 — Save, copy to Drive, file it

1. Save the report to `/mnt/user-data/outputs/` as `{TICKER}_{TRADE-TYPE}_{YYYY-MM-DD}.md` (e.g. `NVDA_LEAPS_2026-08-18.md`).
2. Call `present_files` so Larry can see it.
3. Push a copy to Google Drive using the Drive connector:
   - Folder structure: `Trade Desk / {YYYY-MM} / {TICKER} /` — create the folder path if it doesn't exist yet (check with `search_files` before creating, so you don't spawn duplicate folders each run).
   - Upload with the same filename as the local copy.
4. Confirm to Larry in one line: file saved + Drive location. Don't over-narrate the mechanics.

## Notes on tone

Larry wants this concise, action-oriented, and in his voice — direct, "tapped-in," not overly hedged. The report itself can be thorough (that's the point), but your chat message around it should be short: what you pulled, what the verdict is, where the file landed.
