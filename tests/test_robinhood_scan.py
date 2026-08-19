import pytest

import robinhood_scan as rs


def _rising_bars_with_bullish_engulfing(n=30, base=90.0):
    """n-2 steadily rising bars, then a small red pullback candle, then a
    bullish engulfing candle -- close ends well above the slow-moving
    200-EMA so trend reads BULLISH and the pattern detector fires."""
    bars = []
    for i in range(n - 2):
        o = base + i
        bars.append({"open": o, "high": o + 1.5, "low": o - 0.5, "close": o + 1})
    last_close = bars[-1]["close"]
    # small red pullback
    bars.append({"open": last_close + 0.5, "high": last_close + 0.6, "low": last_close - 1.0, "close": last_close})
    # bullish engulfing: opens below prior close, closes above prior open
    prev = bars[-1]
    bars.append({
        "open": prev["close"] - 0.2,
        "high": prev["open"] + 2.5,
        "low": prev["close"] - 0.3,
        "close": prev["open"] + 2.0,
    })
    return bars


def _flat_bars(n=30, price=50.0):
    return [{"open": price, "high": price, "low": price, "close": price} for _ in range(n)]


def test_evaluate_timeframe_none_with_insufficient_bars():
    assert rs.evaluate_timeframe(_flat_bars(n=10)) is None


def test_evaluate_timeframe_detects_bullish_trend_and_signal():
    result = rs.evaluate_timeframe(_rising_bars_with_bullish_engulfing())
    assert result["trend"] == "BULLISH"
    assert result["bull_signal"] is True


def test_evaluate_confluence_bull_requires_majority_bullish_timeframes():
    bars = _rising_bars_with_bullish_engulfing()
    verdict = rs.evaluate("TEST", {"Weekly": bars, "Daily": bars})
    assert verdict["confluence_bull"] is True
    assert "Daily" in verdict["bull_signal_timeframes"]


def test_evaluate_confluence_bull_false_with_single_timeframe():
    bars = _rising_bars_with_bullish_engulfing()
    # only one timeframe available -> bull_count can be at most 1, never >= 2
    verdict = rs.evaluate("TEST", {"Daily": bars})
    assert verdict["confluence_bull"] is False
    assert "suggested_entry" not in verdict


def test_evaluate_confluence_bull_false_when_no_signal():
    flat = _flat_bars()
    verdict = rs.evaluate("TEST", {"Weekly": flat, "Daily": flat})
    assert verdict["confluence_bull"] is False


def test_evaluate_suggested_entry_and_stop_math():
    bars = _rising_bars_with_bullish_engulfing()
    verdict = rs.evaluate("TEST", {"Weekly": bars, "Daily": bars})
    daily = verdict["timeframes"]["Daily"]
    assert verdict["suggested_entry"] == pytest.approx(round(daily["last_high"] + 0.15, 2))
    assert verdict["suggested_stop"] == pytest.approx(round(daily["last_low"], 2))
    assert verdict["risk_per_share"] == pytest.approx(
        round(verdict["suggested_entry"] - verdict["suggested_stop"], 2)
    )


def test_evaluate_skips_timeframes_with_insufficient_data():
    bars = _rising_bars_with_bullish_engulfing()
    verdict = rs.evaluate("TEST", {"Weekly": bars, "Daily": bars, "Hourly": _flat_bars(n=5)})
    assert set(verdict["timeframes"].keys()) == {"Weekly", "Daily"}
