"""
ROBINHOOD EXECUTION RISK GUARDS
--------------------------------
Pure, network-free risk math for sizing and capping trades placed against a
live Robinhood account through the Robinhood MCP tools (place_equity_order /
review_equity_order). This module makes no network calls and holds no
credentials -- it only computes numbers from inputs the caller already has
(account buying power, today's trade count, today's realized P&L).

This is deliberately kept separate from aristotle_alert_system.py: that
script is a standalone, credential-free scanner that only ever prints
alerts. Anything that can put an order in front of real money lives here,
where the math is small enough to unit test exhaustively.

Defaults encode the account's configured risk limits:
- position_size(): cap any single order at 2% of current buying power
- daily_caps_ok(): stop for the day at 6 trades or a 6% realized loss

Nothing in this module calls place_equity_order. The caller (a Claude
session driving the Robinhood MCP tools) is responsible for calling
review_equity_order with the sized quantity, presenting it to the account
owner, and only calling place_equity_order after explicit confirmation.
"""

import math

MAX_POSITION_PCT = 0.02
MAX_TRADES_PER_DAY = 6
MAX_DAILY_LOSS_PCT = 0.06


def position_size(buying_power, price, max_position_pct=MAX_POSITION_PCT):
    """Max whole+fractional shares (rounded down to 6 decimals, Robinhood's
    fractional-share precision) purchasable within max_position_pct of
    buying_power at the given price. Returns 0.0 for non-positive inputs."""
    if buying_power <= 0 or price <= 0:
        return 0.0
    # min() is a hard floor against buying_power itself: even a misconfigured
    # max_position_pct (e.g. > 1.0) must never size an order beyond what the
    # account can actually afford.
    max_dollars = min(buying_power * max_position_pct, buying_power)
    shares = max_dollars / price
    return math.floor(shares * 1_000_000) / 1_000_000


def daily_caps_ok(
    trades_today,
    realized_pnl_today,
    day_start_equity,
    max_trades=MAX_TRADES_PER_DAY,
    max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
):
    """Returns (ok: bool, reason: str | None). reason is None when ok.

    trades_today: count of orders already placed today on the account.
    realized_pnl_today: signed $ P&L realized today (negative = loss).
    day_start_equity: account equity at the start of the trading day, used
      as the denominator for the loss-percentage cap. If unknown/zero, the
      loss cap is skipped (there's nothing to divide by) but the trade-count
      cap still applies.
    """
    if trades_today >= max_trades:
        return False, f"max trades/day reached ({trades_today}/{max_trades})"

    if day_start_equity > 0:
        loss_pct = -realized_pnl_today / day_start_equity
        if loss_pct >= max_daily_loss_pct:
            return False, (
                f"daily loss cap hit ({loss_pct * 100:.1f}% >= "
                f"{max_daily_loss_pct * 100:.0f}%)"
            )

    return True, None
