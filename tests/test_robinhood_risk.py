import pytest

import robinhood_risk as rr


# ---------------------------------------------------------------------------
# position_size
# ---------------------------------------------------------------------------

def test_position_size_caps_at_max_pct_of_buying_power():
    # $500 buying power, 2% cap -> $10 max notional
    shares = rr.position_size(buying_power=500, price=100, max_position_pct=0.02)
    assert shares == pytest.approx(0.1)
    assert shares * 100 <= 10.0 + 1e-9


def test_position_size_rounds_down_to_six_decimals():
    shares = rr.position_size(buying_power=500, price=3, max_position_pct=0.02)
    # 500*0.02/3 = 3.333333333... -> floor to 6 decimals
    assert shares == 3.333333
    assert shares * 3 <= 500 * 0.02


def test_position_size_zero_on_nonpositive_inputs():
    assert rr.position_size(0, 100) == 0.0
    assert rr.position_size(-50, 100) == 0.0
    assert rr.position_size(500, 0) == 0.0
    assert rr.position_size(500, -10) == 0.0


def test_position_size_never_exceeds_buying_power():
    # pathological: max_position_pct > 1 should still never spend more than exists
    shares = rr.position_size(buying_power=100, price=1, max_position_pct=5.0)
    assert shares * 1 <= 100 + 1e-9


# ---------------------------------------------------------------------------
# daily_caps_ok
# ---------------------------------------------------------------------------

def test_daily_caps_ok_under_all_limits():
    ok, reason = rr.daily_caps_ok(trades_today=2, realized_pnl_today=-5, day_start_equity=500)
    assert ok is True
    assert reason is None


def test_daily_caps_blocks_at_max_trades():
    ok, reason = rr.daily_caps_ok(trades_today=6, realized_pnl_today=0, day_start_equity=500)
    assert ok is False
    assert "trades/day" in reason


def test_daily_caps_blocks_above_max_trades():
    ok, reason = rr.daily_caps_ok(trades_today=7, realized_pnl_today=0, day_start_equity=500)
    assert ok is False


def test_daily_caps_blocks_at_loss_threshold():
    # 6% of 500 = 30 loss
    ok, reason = rr.daily_caps_ok(trades_today=1, realized_pnl_today=-30, day_start_equity=500)
    assert ok is False
    assert "loss cap" in reason


def test_daily_caps_allows_just_under_loss_threshold():
    ok, reason = rr.daily_caps_ok(trades_today=1, realized_pnl_today=-29.99, day_start_equity=500)
    assert ok is True


def test_daily_caps_gains_never_trip_loss_cap():
    ok, reason = rr.daily_caps_ok(trades_today=1, realized_pnl_today=1000, day_start_equity=500)
    assert ok is True


def test_daily_caps_skips_loss_check_with_zero_equity():
    # nothing to divide by -- trade-count cap still applies
    ok, reason = rr.daily_caps_ok(trades_today=1, realized_pnl_today=-999, day_start_equity=0)
    assert ok is True

    ok, reason = rr.daily_caps_ok(trades_today=6, realized_pnl_today=-999, day_start_equity=0)
    assert ok is False
    assert "trades/day" in reason


def test_daily_caps_respects_custom_limits():
    ok, reason = rr.daily_caps_ok(
        trades_today=3, realized_pnl_today=-10, day_start_equity=100,
        max_trades=3, max_daily_loss_pct=0.05,
    )
    assert ok is False
    assert "trades/day" in reason
