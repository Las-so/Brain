import json

import numpy as np
import pandas as pd
import pytest

import aristotle_alert_system as aas


def make_df(rows):
    """rows: list of dicts with open/high/low/close (index becomes a plain
    RangeIndex, which is fine since the module only uses positional access)."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def test_ema_converges_toward_constant_series():
    series = pd.Series([100.0] * 50)
    result = aas.ema(series, 8)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_is_bounded_and_high_for_uptrend():
    series = pd.Series(np.arange(1, 51, dtype=float))
    result = aas.rsi(series, length=14)
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()
    assert valid.iloc[-1] > 90  # strictly rising series -> RSI near 100


def test_macd_hist_is_macd_minus_signal():
    series = pd.Series(np.sin(np.linspace(0, 10, 100)) * 10 + 100)
    macd_line, signal_line, hist = aas.macd(series)
    pd.testing.assert_series_equal(hist, macd_line - signal_line, check_names=False)


def test_fib_golden_pocket_bounds():
    df = make_df([
        {"open": 90, "high": 100, "low": 80, "close": 95},
        {"open": 95, "high": 98, "low": 90, "close": 92},
    ])
    fibs = aas.fib_golden_pocket(df, lookback=60)
    assert fibs["swing_high"] == 100
    assert fibs["swing_low"] == 80
    assert fibs["golden_pocket_low"] < fibs["golden_pocket_high"]
    assert 80 <= fibs["golden_pocket_low"] <= 100


# ---------------------------------------------------------------------------
# Candlestick patterns
# ---------------------------------------------------------------------------

def test_bullish_engulfing_detected():
    df = make_df([
        {"open": 10, "high": 10.2, "low": 9.0, "close": 9.2},   # red
        {"open": 9.0, "high": 10.5, "low": 8.9, "close": 10.3},  # green, engulfs
    ])
    assert aas.is_bullish_engulfing(df) is True
    assert aas.is_bearish_engulfing(df) is False


def test_bearish_engulfing_detected():
    df = make_df([
        {"open": 9.0, "high": 10.2, "low": 8.9, "close": 10.0},  # green
        {"open": 10.1, "high": 10.2, "low": 8.5, "close": 8.6},  # red, engulfs
    ])
    assert aas.is_bearish_engulfing(df) is True
    assert aas.is_bullish_engulfing(df) is False


def test_bullish_pin_bar_detected():
    df = make_df([
        {"open": 9.8, "high": 10.0, "low": 8.0, "close": 9.9},
    ])
    assert aas.is_bullish_pin_bar(df) is True
    assert aas.is_bearish_pin_bar(df) is False


def test_bearish_pin_bar_detected():
    df = make_df([
        {"open": 9.1, "high": 11.0, "low": 9.0, "close": 9.2},
    ])
    assert aas.is_bearish_pin_bar(df) is True
    assert aas.is_bullish_pin_bar(df) is False


def test_no_false_positive_on_doji_flat_range():
    df = make_df([{"open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0}])
    assert aas.is_bullish_pin_bar(df) is False
    assert aas.is_bearish_pin_bar(df) is False


# ---------------------------------------------------------------------------
# Divergence
# ---------------------------------------------------------------------------

def _divergence_df(highs, lows, indicator_values):
    return pd.DataFrame({
        "open": highs, "close": lows,
        "high": highs, "low": lows,
        "rsi14": indicator_values,
    })


def test_bearish_divergence_detected():
    n = 21
    highs = [100 + i for i in range(n - 1)] + [150]   # new price high on last candle
    lows = [h - 1 for h in highs]
    rsi_values = [50 + i * 0.1 for i in range(n - 1)] + [40]  # RSI fails to confirm
    df = _divergence_df(highs, lows, rsi_values)
    assert aas.detect_divergence(df, "rsi14", lookback=20) == "bearish"


def test_bullish_divergence_detected():
    n = 21
    lows = [100 - i for i in range(n - 1)] + [50]     # new price low on last candle
    highs = [l + 1 for l in lows]
    rsi_values = [50 - i * 0.1 for i in range(n - 1)] + [60]  # RSI fails to confirm
    df = _divergence_df(highs, lows, rsi_values)
    assert aas.detect_divergence(df, "rsi14", lookback=20) == "bullish"


def test_no_divergence_when_confirmed():
    n = 21
    highs = [100 + i for i in range(n)]
    lows = [h - 1 for h in highs]
    rsi_values = [50 + i for i in range(n)]
    df = _divergence_df(highs, lows, rsi_values)
    assert aas.detect_divergence(df, "rsi14", lookback=20) is None


def test_divergence_returns_none_with_insufficient_data():
    df = _divergence_df([100, 101], [99, 100], [50, 51])
    assert aas.detect_divergence(df, "rsi14", lookback=20) is None


# ---------------------------------------------------------------------------
# Position evaluation (pure logic, no network)
# ---------------------------------------------------------------------------

def test_evaluate_position_stop_hit():
    pos = {"entry": 100, "stop": 90, "shares": 100, "targets": [[1.0, 0.5]]}
    status = aas.evaluate_position("TEST", pos, price=89, ema8=95, ema21=93, swing_low_10=88)
    assert status.stopped_out is True
    assert status.targets_hit == []
    assert status.trail_level is None


def test_evaluate_position_target_reached():
    pos = {"entry": 100, "stop": 90, "shares": 100, "targets": [[1.0, 0.5], [2.0, 0.25]]}
    # 1R = 10; price at 110 => current_r = 1.0, only first target hit
    status = aas.evaluate_position("TEST", pos, price=110, ema8=105, ema21=102, swing_low_10=100)
    assert status.stopped_out is False
    assert status.current_r == pytest.approx(1.0)
    assert status.targets_hit == [(1.0, 0.5, 50)]


def test_evaluate_position_trailing_21ema():
    pos = {
        "entry": 100, "stop": 90, "shares": 100,
        "targets": [[1.0, 0.5]], "trail_after_R": 2.0, "trail_method": "21ema",
    }
    status = aas.evaluate_position("TEST", pos, price=125, ema8=120, ema21=118, swing_low_10=115)
    assert status.current_r == pytest.approx(2.5)
    assert status.trail_level == 118
    assert status.trail_method == "21ema"


def test_evaluate_position_trailing_swing_low():
    pos = {
        "entry": 100, "stop": 90, "shares": 100,
        "targets": [], "trail_after_R": 1.0, "trail_method": "swing_low",
    }
    status = aas.evaluate_position("TEST", pos, price=115, ema8=112, ema21=110, swing_low_10=108)
    assert status.trail_level == 108
    assert status.trail_method == "swing_low"


def test_evaluate_position_rejects_stop_above_entry():
    pos = {"entry": 100, "stop": 105, "shares": 10, "targets": []}
    with pytest.raises(ValueError):
        aas.evaluate_position("TEST", pos, price=101, ema8=100, ema21=100, swing_low_10=100)


# ---------------------------------------------------------------------------
# fetch() retry behavior
# ---------------------------------------------------------------------------

def test_fetch_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}
    good_df = pd.DataFrame({"Open": [1, 2], "High": [1, 2], "Low": [1, 2], "Close": [1, 2], "Volume": [1, 2]})

    def flaky_download(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("simulated network failure")
        return good_df

    monkeypatch.setattr(aas.yf, "download", flaky_download)
    monkeypatch.setattr(aas.time, "sleep", lambda *_: None)

    result = aas.fetch("TEST", retries=3, backoff=1)
    assert result is not None
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert calls["n"] == 2


def test_fetch_gives_up_after_max_retries(monkeypatch):
    def always_fails(*args, **kwargs):
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr(aas.yf, "download", always_fails)
    monkeypatch.setattr(aas.time, "sleep", lambda *_: None)

    result = aas.fetch("TEST", retries=3, backoff=1)
    assert result is None


def test_fetch_flattens_multiindex_columns(monkeypatch):
    columns = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], ["TEST"]])
    df = pd.DataFrame([[1, 1, 1, 1, 100]], columns=columns)

    monkeypatch.setattr(aas.yf, "download", lambda *a, **k: df)
    result = aas.fetch("TEST", retries=1)
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def test_load_config_reads_json_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "watchlist": ["ABC"],
        "positions": {"ABC": {"entry": 1, "stop": 0.5, "shares": 1, "targets": []}},
    }))
    watchlist, positions = aas.load_config(str(config_path))
    assert watchlist == ["ABC"]
    assert "ABC" in positions


def test_load_config_falls_back_to_defaults_when_missing(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"
    watchlist, positions = aas.load_config(str(missing_path))
    assert watchlist == aas.WATCHLIST
    assert positions == aas.POSITIONS


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def test_notify_noop_without_webhook_url(monkeypatch):
    called = {"hit": False}
    monkeypatch.setattr(aas.requests, "post", lambda *a, **k: called.__setitem__("hit", True))
    aas.notify("hello", "")
    assert called["hit"] is False


def test_notify_posts_slack_payload(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(aas.requests, "post", fake_post)
    aas.notify("hello", "https://hooks.slack.com/services/xxx")
    assert captured["json"] == {"text": "hello"}


def test_notify_posts_discord_payload(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(aas.requests, "post", fake_post)
    aas.notify("hello", "https://discord.com/api/webhooks/xxx")
    assert captured["json"] == {"content": "hello"}


def test_notify_swallows_request_exceptions(monkeypatch):
    def fake_post(*a, **k):
        raise ConnectionError("down")

    monkeypatch.setattr(aas.requests, "post", fake_post)
    # should not raise
    aas.notify("hello", "https://hooks.slack.com/services/xxx")
