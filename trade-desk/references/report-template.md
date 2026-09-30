# Trade Report Template

Fill every section with real pulled data. If something's unavailable, write "not available via RobinHood" rather than skipping it silently.

```markdown
# {TICKER} — {Trade Type: Stock Sundays / Trading Bondsman} — {YYYY-MM-DD}

## Snapshot
- Current price / day range / volume
- Sector / market cap (if relevant)
- Existing position (if any): size, avg cost, current P&L

## Top-Down Read (Stock Sundays only)
Weekly / Daily / 5-min notes + SPY/QQQ/IWM alignment

## Screening Filters (Trading Bondsman only)
Underlying → Liquidity → Expiration → Delta/Strike → IV

## Framework Checklist
(Pull the exact checklist from the relevant reference file, checked/filled with real numbers)

## Risk Plan
- Position sizing (thirds, or LEAPS contract count/allocation)
- Stop / invalidation level
- $ risk (per unit and total)

## Verdict
**Take / Watch / Pass** — one or two lines on why

## Data Sources
Note which RobinHood endpoints were pulled and the timestamp
```
