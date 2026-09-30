# Trading Bondsman — LEAPS Screening & Profitability Framework

Long-dated options (LEAPS) as a stock-replacement / leveraged-conviction play, screened for actual profitability rather than just "this looks bullish." This reference is a living document — Larry's glossary and filters should get folded in here as they're refined further; treat what's below as the working baseline.

## Screening filters (apply in order, cut names that fail)

1. **Underlying quality** — is this a name Larry actually wants long-term exposure to (fundamentals, sector, conviction), not just a hot ticker?
2. **Liquidity** — option chain needs real volume/open interest and a tight bid/ask spread. Wide spreads eat profitability even on a correct thesis.
3. **Expiration** — true LEAPS: 12+ months out, ideally giving the thesis 18-24 months of runway to play out without theta becoming the dominant force too early.
4. **Delta / strike selection** — favor deep ITM (delta roughly 0.70-0.85) to behave more like stock-replacement with lower theta decay and less reliance on IV expansion, unless the play is explicitly a higher-leverage/higher-risk bet (flag this distinction in the report).
5. **Implied volatility** — check IV relative to that name's own IV history (IV rank/percentile). Buying LEAPS when IV is elevated means paying up for premium that mean-reverts against you even if direction is right.

## Profitability filters

- **Cost basis vs. stock-equivalent**: what % of the notional stock price is the LEAPS costing? Lower is more efficient leverage.
- **Breakeven price**: strike + premium paid. How far is that from current price, and is that move realistic in the timeframe given the stock's historical volatility?
- **Required move for a target return**: e.g., what underlying move is needed to double the contract, and does that align with a real catalyst (earnings, product cycle, macro) inside the expiration window?
- **Earnings exposure**: how many earnings prints fall inside the holding window — each one is a volatility event that cuts both ways.

## Checklist to fill in the report

- [ ] Underlying conviction: why this name, long-term thesis in one line
- [ ] Liquidity check: OI/volume/spread — pass/fail
- [ ] Expiration selected: ____ (months out)
- [ ] Strike & delta: ____ / ____
- [ ] IV rank/percentile at time of screen: ____
- [ ] Cost basis as % of stock price: ____
- [ ] Breakeven price: ____ (____ % move required)
- [ ] Earnings prints inside window: ____ (dates)
- [ ] Target return scenario and move required to hit it
- [ ] Verdict: Take / Watch / Pass
