"""
TYPESAFE SETUP GRADING
----------------------
Turns the binary confluence gate in robinhood_scan.evaluate() into a graded
judgment, so a watchlist can be *ranked* instead of merely filtered.

Today robinhood_scan collapses a setup to:

    confluence_bull = bool(bull_signal_timeframes) and bull_count >= 2

That treats "Daily bull pin bar inside the golden pocket with both timeframes
trending up" and "Weekly trend up by a penny plus one marginal engulfing" as
the same answer: True. Both clear the gate; only one is worth risking money on.

This module keeps every number in code -- EMA/RSI/MACD, Fibonacci levels, the
15-cent rule, position sizing, the daily caps -- and asks TypeSafe only the
judgment that the indicator math cannot express: how well does this assembled
evidence match the framework's description of a high-quality long entry.

Design notes:
- It places no orders and fetches no market data. It reads a verdict dict from
  robinhood_scan.evaluate() and returns a grade. Sizing still goes through
  robinhood_risk.position_size(); execution still requires the account owner.
- Every question and every threshold lives in this file, in QUESTIONS and
  GRADE_THRESHOLDS, so they can be reviewed in one place rather than hunted
  for across the codebase.
- Transport is injected (the `ask` argument). This module builds state,
  composes answers, and applies policy; it does not own the HTTP contract, so
  it needs no credentials and is fully testable offline. The HTTP `ask`
  implementation is deliberately not included yet: it must be written against
  the current TypeSafe API reference rather than guessed at, since a wrong
  field name would fail at runtime against real money. See `ask`'s contract in
  grade_setup() for the shape it must satisfy.
"""

# --- Reviewable constants: the questions and the policy ----------------------
#
# Question ids are for this code only; they are not sent to the model, so each
# question carries its full meaning in its own text.

SETUP_QUALITY = "setup_quality"
TREND_AGREEMENT = "trend_agreement"
SIGNAL_IS_MARGINAL = "signal_is_marginal"
LOCATION_IS_GOOD = "location_is_good"

QUESTIONS = {
    SETUP_QUALITY: {
        "type": "score",
        "instructions": (
            "Grade how well this multi-timeframe technical setup matches a "
            "high-quality long swing entry in the Aristotle Investments / "
            "'Trading Bondsman' framework: top-down timeframe agreement, price "
            "above the 200 EMA, a reversal candle or indicator divergence "
            "confirming the entry, and price sitting in the 61.8% Fibonacci "
            "golden pocket rather than extended away from it. Judge only the "
            "evidence given; do not assume facts that are absent."
        ),
        "criteria": {
            "excellent": (
                "Every timeframe supplied trends bullish, a reversal signal "
                "fires on the entry timeframe, and price is in the golden "
                "pocket. Little is left to hope for."
            ),
            "good": (
                "Timeframes agree bullish and a reversal signal fires, but "
                "location is imperfect -- price is outside the golden pocket, "
                "or RSI is already stretched toward overbought."
            ),
            "marginal": (
                "Some bullish evidence, but it is thin or mixed: a signal on "
                "only one timeframe, a trend that barely holds the 200 EMA, or "
                "a bearish signal firing somewhere alongside the bullish one."
            ),
            "poor": (
                "The bullish case rests on one weak signal, or the timeframes "
                "disagree about direction."
            ),
            "no_setup": (
                "No meaningful bullish evidence, or the evidence points short."
            ),
        },
    },
    TREND_AGREEMENT: {
        "type": "choice",
        "instructions": (
            "Across the timeframes supplied, how do the trend readings relate "
            "to one another? Base this only on the reported trend per "
            "timeframe."
        ),
        "criteria": {
            "aligned_bullish": "Every timeframe supplied reads bullish.",
            "aligned_bearish": "Every timeframe supplied reads bearish.",
            "higher_timeframe_leads_bullish": (
                "The longer timeframe is bullish while a shorter one is not, "
                "i.e. a pullback inside a larger uptrend."
            ),
            "conflicted": (
                "The timeframes disagree in a way that does not resolve into a "
                "pullback within a larger uptrend."
            ),
        },
    },
    SIGNAL_IS_MARGINAL: {
        "type": "noul",
        "instructions": (
            "The bullish signal on the entry timeframe is marginal -- it rests "
            "on a single weak trigger, or a bearish signal fires on the same "
            "timeframe and contradicts it."
        ),
    },
    LOCATION_IS_GOOD: {
        "type": "noul",
        "instructions": (
            "Price is at a favourable entry location for a long: inside the "
            "61.8% Fibonacci golden pocket, and not already stretched into "
            "overbought territory on RSI."
        ),
    },
}

# Score levels, worst to best. Order matters: index is the rank.
GRADE_LEVELS = ["no_setup", "poor", "marginal", "good", "excellent"]

# Policy thresholds. These are starting points chosen to be conservative, NOT
# validated numbers -- evaluate them against your own logged setups and
# outcomes before trusting them with size.
GRADE_THRESHOLDS = {
    # Minimum setup_quality level to treat a setup as tradeable at all.
    "min_grade": "good",
    # Below this confidence on setup_quality, the grade is too diffuse to act
    # on alone; route to manual chart review instead.
    "min_confidence": 0.60,
    # At or above this probability that the signal is marginal, veto the setup
    # regardless of its grade. A separate hard condition, deliberately not
    # folded into a weighted average -- "any serious defect" is a veto rule,
    # not something a strong score elsewhere should compensate for.
    "marginal_veto": 0.60,
    # Location is a preference, not a veto: below this, the setup is still
    # tradeable but flagged as a worse entry price.
    "good_location": 0.50,
}


class Verdict:
    """Outcome of grading. Kept as a small object so callers read fields by
    name instead of indexing a tuple."""

    TRADEABLE = "tradeable"
    REVIEW = "needs_manual_review"
    REJECTED = "rejected"

    def __init__(self, action, grade, confidence, reasons, raw):
        self.action = action
        self.grade = grade
        self.confidence = confidence
        self.reasons = reasons
        self.raw = raw

    def as_dict(self):
        return {
            "action": self.action,
            "grade": self.grade,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "raw": self.raw,
        }

    def __repr__(self):
        return f"<Verdict {self.action} grade={self.grade} conf={self.confidence}>"


def build_state(verdict):
    """Convert a robinhood_scan.evaluate() verdict into named state fields.

    Named fields (rather than one blob of prose) keep each piece of evidence
    addressable, and keep the numbers exactly as the indicator math produced
    them.
    """
    timeframes = {}
    for label, tf in verdict.get("timeframes", {}).items():
        timeframes[label] = {
            "trend": tf["trend"],
            "rsi14": tf["rsi14"],
            "bullish_reversal_signal": tf["bull_signal"],
            "bearish_reversal_signal": tf["bear_signal"],
            "price_in_fib_golden_pocket": tf["in_golden_pocket"],
            "last_close": tf["last_close"],
        }

    state = {
        "symbol": verdict["symbol"],
        "entry_timeframe": "Daily",
        "timeframes": timeframes,
        "timeframes_with_bullish_signal": verdict.get("bull_signal_timeframes", []),
    }

    # Only present when the existing code found confluence; absent is
    # meaningful information, so don't invent a placeholder.
    if "suggested_entry" in verdict:
        state["proposed_trade"] = {
            "entry": verdict["suggested_entry"],
            "stop": verdict["suggested_stop"],
            "risk_per_share": verdict["risk_per_share"],
            "entry_rule": "15-cent rule: prior Daily high + $0.15",
        }

    return state


def grade_setup(verdict, ask, thresholds=None):
    """Grade a scan verdict and apply policy.

    verdict: dict from robinhood_scan.evaluate().
    ask: callable(state, questions) -> {question_id: answer}, where each
        answer is {"value": str, "confidence": float} for a score/choice
        question and {"probability": float} for a noul. Injected so this
        module stays free of transport concerns and is testable without
        network access.
    thresholds: override GRADE_THRESHOLDS for tuning or testing.

    All four questions are independent judgments over the same state, so they
    go in a single request and run in parallel.
    """
    thresholds = {**GRADE_THRESHOLDS, **(thresholds or {})}

    if not verdict.get("timeframes"):
        return Verdict(
            Verdict.REJECTED,
            grade=None,
            confidence=None,
            reasons=["no timeframe had enough history to evaluate"],
            raw={},
        )

    state = build_state(verdict)
    answers = ask(state, QUESTIONS)

    quality = answers[SETUP_QUALITY]
    grade = quality["value"]
    confidence = quality["confidence"]
    marginal = answers[SIGNAL_IS_MARGINAL]["probability"]
    good_location = answers[LOCATION_IS_GOOD]["probability"]
    trend = answers[TREND_AGREEMENT]["value"]

    raw = {
        "setup_quality": grade,
        "setup_quality_confidence": confidence,
        "trend_agreement": trend,
        "p_signal_is_marginal": marginal,
        "p_location_is_good": good_location,
    }

    reasons = []

    # Veto first: a serious defect is not something a high grade compensates
    # for, so this is a separate condition rather than a weighted term.
    if marginal >= thresholds["marginal_veto"]:
        reasons.append(
            f"signal judged marginal (p={marginal:.2f} >= "
            f"{thresholds['marginal_veto']:.2f})"
        )
        return Verdict(Verdict.REJECTED, grade, confidence, reasons, raw)

    if _rank(grade) < _rank(thresholds["min_grade"]):
        reasons.append(
            f"grade {grade!r} below minimum {thresholds['min_grade']!r}"
        )
        return Verdict(Verdict.REJECTED, grade, confidence, reasons, raw)

    # Grade clears the bar, but a diffuse distribution means the model did not
    # settle between levels. That is a reason to look at the chart, not to
    # reject a setup that may well be fine.
    if confidence < thresholds["min_confidence"]:
        reasons.append(
            f"grade {grade!r} but confidence {confidence:.2f} < "
            f"{thresholds['min_confidence']:.2f}"
        )
        return Verdict(Verdict.REVIEW, grade, confidence, reasons, raw)

    if trend == "conflicted":
        reasons.append("timeframes conflicted on direction")
        return Verdict(Verdict.REVIEW, grade, confidence, reasons, raw)

    reasons.append(f"grade {grade!r} at confidence {confidence:.2f}")
    if good_location < thresholds["good_location"]:
        # A preference, not a gate: still tradeable, worse entry price.
        reasons.append(
            f"entry location unfavourable (p={good_location:.2f}) -- "
            "expect a worse fill than the framework's ideal"
        )
    if trend == "higher_timeframe_leads_bullish":
        reasons.append("pullback within a larger uptrend")

    return Verdict(Verdict.TRADEABLE, grade, confidence, reasons, raw)


def rank_setups(verdicts, ask, thresholds=None):
    """Grade several scan verdicts and return them best-first.

    This is the point of grading rather than gating: with a graded answer the
    watchlist becomes an ordered queue, so attention goes to the best setup
    available instead of to whichever ticker happens to be alphabetically
    first among those that passed a boolean.
    """
    graded = [(v["symbol"], grade_setup(v, ask, thresholds)) for v in verdicts]
    graded.sort(
        key=lambda pair: (
            _rank(pair[1].grade),
            pair[1].confidence or 0.0,
        ),
        reverse=True,
    )
    return graded


def _rank(grade):
    """Ordinal position of a grade level; -1 for None/unknown so it sorts last."""
    try:
        return GRADE_LEVELS.index(grade)
    except ValueError:
        return -1
