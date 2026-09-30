"""
TYPESAFE LIVE SMOKE TEST
------------------------
One real call against the TypeSafe API, so the integration is verified rather
than merely plausible. typesafe_client.py has never made a live call; until
this script runs clean, the field names inside each answer object are taken
from documentation rather than observation.

    export TYPESAFE_API_KEY=...
    python scripts/typesafe_smoke.py

It prints the raw answers alongside the graded verdict. Check that:
  - every question came back (no 422 about a malformed question),
  - _normalize_answer() in typesafe_client.py read each answer correctly,
  - the grade and probabilities are plausible for the fixture below.

Uses a hand-built fixture, not live market data, so it costs one request and
needs no network access to a broker.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typesafe_client import TypeSafeError, ask
from typesafe_grade import QUESTIONS, build_state, grade_setup

# A textbook setup: both timeframes bullish, Daily reversal signal firing with
# price in the golden pocket. If this does not grade well, either the questions
# or the normalization needs work.
FIXTURE = {
    "symbol": "SPY",
    "timeframes": {
        "Weekly": {
            "trend": "BULLISH", "rsi14": 58.2, "bull_signal": False,
            "bear_signal": False, "in_golden_pocket": False,
            "last_close": 515.0, "last_high": 517.0, "last_low": 509.0,
        },
        "Daily": {
            "trend": "BULLISH", "rsi14": 47.5, "bull_signal": True,
            "bear_signal": False, "in_golden_pocket": True,
            "last_close": 515.0, "last_high": 515.0, "last_low": 505.0,
        },
    },
    "confluence_bull": True,
    "bull_signal_timeframes": ["Daily"],
    "suggested_entry": 515.15,
    "suggested_stop": 505.0,
    "risk_per_share": 10.15,
}


def main():
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("TYPESAFE_API_KEY is not set.", file=sys.stderr)
        return 2

    print("state sent:")
    print(json.dumps(build_state(FIXTURE), indent=2))

    raw = {}

    def recording_ask(state, questions):
        answers = ask(state, questions)
        raw.update(answers)
        return answers

    try:
        verdict = grade_setup(FIXTURE, recording_ask)
    except TypeSafeError as exc:
        print(f"\nAPI call failed: {exc}", file=sys.stderr)
        return 1

    print("\nnormalized answers:")
    print(json.dumps(raw, indent=2))
    print("\nverdict:")
    print(json.dumps(verdict.as_dict(), indent=2))
    print(f"\n{len(QUESTIONS)} questions asked in 1 request.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
