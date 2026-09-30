"""Policy tests for typesafe_grade. No network and no API key: `ask` is
injected, so every branch of the composition is exercised against canned
answers."""

import pytest

from typesafe_grade import (
    GRADE_LEVELS,
    LOCATION_IS_GOOD,
    QUESTIONS,
    SETUP_QUALITY,
    SIGNAL_IS_MARGINAL,
    TREND_AGREEMENT,
    Verdict,
    build_state,
    grade_setup,
    rank_setups,
)


def fake_ask(grade="excellent", confidence=0.9, marginal=0.05,
             location=0.9, trend="aligned_bullish"):
    """Build an `ask` callable returning fixed answers, and record the state it
    was handed so tests can assert on what would have been sent."""
    calls = []

    def ask(state, questions):
        calls.append((state, questions))
        return {
            SETUP_QUALITY: {"value": grade, "confidence": confidence},
            TREND_AGREEMENT: {"value": trend, "confidence": 0.8},
            SIGNAL_IS_MARGINAL: {"probability": marginal},
            LOCATION_IS_GOOD: {"probability": location},
        }

    ask.calls = calls
    return ask


def verdict(symbol="SPY", with_trade=True, timeframes=None):
    if timeframes is None:
        timeframes = {
            "Weekly": _tf(trend="BULLISH"),
            "Daily": _tf(trend="BULLISH", bull_signal=True, in_golden_pocket=True),
        }
    v = {
        "symbol": symbol,
        "timeframes": timeframes,
        "confluence_bull": True,
        "bull_signal_timeframes": [
            tf for tf, r in timeframes.items() if r["bull_signal"]
        ],
    }
    if with_trade:
        v.update(suggested_entry=515.15, suggested_stop=505.0, risk_per_share=10.15)
    return v


def _tf(trend="BULLISH", bull_signal=False, bear_signal=False,
        in_golden_pocket=False, rsi14=55.0):
    return {
        "trend": trend,
        "rsi14": rsi14,
        "bull_signal": bull_signal,
        "bear_signal": bear_signal,
        "in_golden_pocket": in_golden_pocket,
        "last_close": 515.0,
        "last_high": 515.0,
        "last_low": 505.0,
    }


# --- state building ---------------------------------------------------------

def test_build_state_carries_every_timeframe_and_renames_signal_fields():
    state = build_state(verdict())
    assert state["symbol"] == "SPY"
    assert set(state["timeframes"]) == {"Weekly", "Daily"}
    daily = state["timeframes"]["Daily"]
    assert daily["bullish_reversal_signal"] is True
    assert daily["price_in_fib_golden_pocket"] is True
    assert daily["rsi14"] == 55.0


def test_build_state_omits_proposed_trade_when_scan_found_no_confluence():
    state = build_state(verdict(with_trade=False))
    assert "proposed_trade" not in state


def test_build_state_preserves_exact_numbers_from_indicator_math():
    state = build_state(verdict())
    assert state["proposed_trade"]["entry"] == 515.15
    assert state["proposed_trade"]["risk_per_share"] == 10.15


def test_all_questions_are_sent_in_a_single_request():
    ask = fake_ask()
    grade_setup(verdict(), ask)
    assert len(ask.calls) == 1, "independent questions must not be serialised"
    assert set(ask.calls[0][1]) == set(QUESTIONS)


# --- policy -----------------------------------------------------------------

def test_strong_setup_is_tradeable():
    v = grade_setup(verdict(), fake_ask())
    assert v.action == Verdict.TRADEABLE
    assert v.grade == "excellent"


def test_marginal_signal_vetoes_even_an_excellent_grade():
    """A veto is a separate hard condition: a high grade must not compensate
    for it."""
    v = grade_setup(verdict(), fake_ask(grade="excellent", confidence=0.95,
                                       marginal=0.75))
    assert v.action == Verdict.REJECTED
    assert any("marginal" in r for r in v.reasons)


def test_grade_below_minimum_is_rejected():
    v = grade_setup(verdict(), fake_ask(grade="marginal"))
    assert v.action == Verdict.REJECTED


def test_low_confidence_routes_to_review_not_rejection():
    v = grade_setup(verdict(), fake_ask(grade="good", confidence=0.4))
    assert v.action == Verdict.REVIEW


def test_conflicted_trends_route_to_review():
    v = grade_setup(verdict(), fake_ask(trend="conflicted"))
    assert v.action == Verdict.REVIEW


def test_bad_location_is_a_preference_not_a_gate():
    v = grade_setup(verdict(), fake_ask(location=0.1))
    assert v.action == Verdict.TRADEABLE
    assert any("location" in r for r in v.reasons)


def test_no_usable_timeframes_is_rejected_without_calling_the_model():
    ask = fake_ask()
    v = grade_setup({"symbol": "SPY", "timeframes": {}}, ask)
    assert v.action == Verdict.REJECTED
    assert ask.calls == [], "must not spend a request on unevaluable input"


def test_thresholds_are_overridable_for_tuning():
    lenient = grade_setup(verdict(), fake_ask(grade="marginal"),
                          thresholds={"min_grade": "marginal"})
    assert lenient.action == Verdict.TRADEABLE


def test_veto_boundary_is_inclusive():
    at = grade_setup(verdict(), fake_ask(marginal=0.60))
    just_under = grade_setup(verdict(), fake_ask(marginal=0.59))
    assert at.action == Verdict.REJECTED
    assert just_under.action == Verdict.TRADEABLE


def test_raw_answers_are_kept_for_later_reuse():
    """Raw judgments stay available so weights and thresholds can change
    without re-running inference."""
    v = grade_setup(verdict(), fake_ask())
    assert v.raw["p_signal_is_marginal"] == 0.05
    assert v.raw["trend_agreement"] == "aligned_bullish"


# --- ranking ----------------------------------------------------------------

def test_ranking_orders_by_grade_then_confidence():
    answers = {
        "AAA": ("good", 0.7),
        "BBB": ("excellent", 0.8),
        "CCC": ("good", 0.9),
    }

    def ask(state, questions):
        grade, conf = answers[state["symbol"]]
        return {
            SETUP_QUALITY: {"value": grade, "confidence": conf},
            TREND_AGREEMENT: {"value": "aligned_bullish", "confidence": 0.8},
            SIGNAL_IS_MARGINAL: {"probability": 0.05},
            LOCATION_IS_GOOD: {"probability": 0.9},
        }

    ranked = rank_setups([verdict(s) for s in answers], ask)
    assert [sym for sym, _ in ranked] == ["BBB", "CCC", "AAA"]


def test_grade_levels_are_ordered_worst_to_best():
    assert GRADE_LEVELS[0] == "no_setup"
    assert GRADE_LEVELS[-1] == "excellent"


def test_score_criteria_cover_every_grade_level():
    """A level the model can return but code cannot rank would sort last
    silently."""
    assert set(QUESTIONS[SETUP_QUALITY]["criteria"]) == set(GRADE_LEVELS)
