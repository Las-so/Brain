"""
BRAIN MCP SERVER
----------------
Exposes the Aristotle Alert System scan/position logic and the Robinhood
risk-sizing guards as MCP tools, so an MCP client (Claude Desktop, a Claude
Agent SDK session, mcp inspector, etc.) can call them directly instead of
shelling out to the standalone scripts.

This server wraps the existing pure functions in aristotle_alert_system.py,
robinhood_scan.py, and robinhood_risk.py -- it adds no new trading logic and
places no trades. Tools that fetch market data (scan_ticker, check_position,
run_watchlist_scan) need network access (yfinance); the rest are pure math
over caller-supplied numbers/bars.

Run under the MCP inspector for interactive testing:
    mcp dev mcp_server.py

Run directly over stdio (for a real MCP client config, e.g. Claude Desktop's
claude_desktop_config.json "command"/"args"):
    python mcp_server.py
"""

import dataclasses
from typing import Optional

from mcp.server.fastmcp import FastMCP

import aristotle_alert_system as aas
import robinhood_risk
import robinhood_scan

mcp = FastMCP("brain")


@mcp.tool()
def scan_ticker(ticker: str) -> dict:
    """Run the Weekly/Daily/4-Hour top-down scan for one ticker via yfinance.

    Returns per-timeframe trend/RSI/pattern results plus any confluence
    alerts and 15-cent-rule entry suggestion. Reads market data only; places
    no trades.
    """
    alerts: list[str] = []
    results = aas.scan_ticker(ticker, alerts=alerts)
    return {"ticker": ticker, "timeframes": results, "alerts": alerts}


@mcp.tool()
def check_position(
    ticker: str,
    entry: float,
    stop: float,
    shares: float,
    targets: Optional[list[list[float]]] = None,
    trail_after_r: Optional[float] = None,
    trail_method: str = "21ema",
) -> dict:
    """Fetch current daily data for `ticker` and evaluate an open position.

    `targets` is a list of [R-multiple, fraction_of_original_size], e.g.
    [[1.0, 0.33], [2.0, 0.33]]. Returns current R-multiple, whether the stop
    was hit, which targets have been reached, and any trailing-stop level.
    """
    pos = {"entry": entry, "stop": stop, "shares": shares, "targets": targets or []}
    if trail_after_r is not None:
        pos["trail_after_R"] = trail_after_r
    pos["trail_method"] = trail_method

    df = aas.fetch(ticker, period="6mo", interval="1d")
    if df is None:
        raise ValueError(f"could not fetch data for {ticker}")
    df = aas.add_indicators(df)
    last = df.iloc[-1]
    swing_low_10 = df["low"].tail(10).min()

    status = aas.evaluate_position(ticker, pos, last["close"], last["ema8"], last["ema21"], swing_low_10)
    return dataclasses.asdict(status)


@mcp.tool()
def evaluate_confluence(symbol: str, timeframes: dict[str, list[dict]]) -> dict:
    """Evaluate a confluence verdict from caller-supplied OHLCV bars.

    Runs the same trend/pattern/divergence logic as scan_ticker, but on bars
    the caller already fetched (e.g. from Robinhood) instead of yfinance --
    no network call. `timeframes` maps a label (e.g. "Weekly", "Daily") to a
    chronologically-ordered list of {"open", "high", "low", "close"} bars.
    """
    return robinhood_scan.evaluate(symbol, timeframes)


@mcp.tool()
def size_position(
    buying_power: float,
    price: float,
    max_position_pct: float = robinhood_risk.MAX_POSITION_PCT,
) -> float:
    """Max shares (fractional, 6 decimal places) purchasable within
    max_position_pct of buying_power at price. Pure risk-sizing math, no
    network call and no order placement."""
    return robinhood_risk.position_size(buying_power, price, max_position_pct)


@mcp.tool()
def check_daily_caps(
    trades_today: int,
    realized_pnl_today: float,
    day_start_equity: float,
    max_trades: int = robinhood_risk.MAX_TRADES_PER_DAY,
    max_daily_loss_pct: float = robinhood_risk.MAX_DAILY_LOSS_PCT,
) -> dict:
    """Check whether today's trade count and realized P&L are still within
    the account's configured daily risk caps. Returns {"ok": bool, "reason":
    str | None}."""
    ok, reason = robinhood_risk.daily_caps_ok(
        trades_today, realized_pnl_today, day_start_equity, max_trades, max_daily_loss_pct,
    )
    return {"ok": ok, "reason": reason}


@mcp.tool()
def get_config(config_path: str = "config.json") -> dict:
    """Load the watchlist and open positions from a JSON config file,
    falling back to the in-script defaults if the file doesn't exist."""
    watchlist, positions = aas.load_config(config_path)
    return {"watchlist": watchlist, "positions": positions}


@mcp.tool()
def run_watchlist_scan(config_path: str = "config.json") -> dict:
    """Scan every ticker in the configured watchlist and check every
    configured open position via yfinance, returning all confluence/stop/
    target/trailing alerts in one call. Reads market data only; sends no
    webhook notification and places no trades."""
    watchlist, positions = aas.load_config(config_path)
    alerts: list[str] = []
    per_ticker = {ticker: aas.scan_ticker(ticker, alerts=alerts) for ticker in watchlist}
    aas.check_positions(positions, alerts=alerts)
    return {"watchlist": watchlist, "results": per_ticker, "alerts": alerts}


if __name__ == "__main__":
    mcp.run()
