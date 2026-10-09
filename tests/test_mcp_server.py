import asyncio
import json

import mcp_server


def _call(tool_name, **kwargs):
    """Call an MCP tool and return its parsed result (JSON dict/list/scalar)."""
    result = asyncio.run(mcp_server.mcp.call_tool(tool_name, kwargs))
    content = result[0] if isinstance(result, tuple) else result
    text = content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def test_lists_all_expected_tools():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "scan_ticker",
        "check_position",
        "evaluate_confluence",
        "size_position",
        "check_daily_caps",
        "get_config",
        "run_watchlist_scan",
    }


def test_size_position_tool_matches_underlying_function():
    import robinhood_risk as rr

    result = _call("size_position", buying_power=500, price=100, max_position_pct=0.02)
    assert float(result) == rr.position_size(500, 100, 0.02)


def test_check_daily_caps_tool_reports_blocked_reason():
    result = _call(
        "check_daily_caps", trades_today=6, realized_pnl_today=0, day_start_equity=500,
    )
    assert result["ok"] is False
    assert "trades/day" in result["reason"]


def test_check_daily_caps_tool_ok_within_limits():
    result = _call(
        "check_daily_caps", trades_today=1, realized_pnl_today=-5, day_start_equity=500,
    )
    assert result == {"ok": True, "reason": None}


def test_get_config_tool_reads_example_config():
    result = _call("get_config", config_path="config.example.json")
    assert result["watchlist"] == ["SPY", "QQQ", "TSLA", "NVDA", "AAPL", "AMZN"]
    assert "TSLA" in result["positions"]


def test_get_config_tool_falls_back_to_defaults_for_missing_file():
    import aristotle_alert_system as aas

    result = _call("get_config", config_path="no_such_config.json")
    assert result["watchlist"] == aas.WATCHLIST
    assert result["positions"] == aas.POSITIONS


def test_evaluate_confluence_tool_matches_underlying_function():
    import robinhood_scan

    bars = [
        {"open": 100 + i * 0.1, "high": 101 + i * 0.1, "low": 99 + i * 0.1, "close": 100.5 + i * 0.1}
        for i in range(40)
    ]
    timeframes = {"Daily": bars, "Weekly": bars}

    result = _call("evaluate_confluence", symbol="TEST", timeframes=timeframes)
    assert result == robinhood_scan.evaluate("TEST", timeframes)
