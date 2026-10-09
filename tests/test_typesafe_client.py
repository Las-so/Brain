"""Tests for the TypeSafe HTTP client. urlopen is stubbed, so these run with no
network and no API key -- they pin the request envelope, the error mapping, the
retry policy, and the answer normalization, none of which need a live call.

They do NOT prove the integration works against the real API; only
scripts/typesafe_smoke.py can do that."""

import io
import json
import urllib.error

import pytest

import typesafe_client
from typesafe_client import (
    AnswerShapeError,
    TypeSafeError,
    _normalize_answer,
    ask,
)

QUESTIONS = {
    "grade": {"type": "score", "instructions": "..."},
    "flag": {"type": "noul", "instructions": "..."},
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def stub_urlopen(monkeypatch, body=None, errors=()):
    """Stub urlopen; record each request. `errors` are raised in order before
    `body` is finally returned."""
    calls = []
    pending = list(errors)

    def fake(request, timeout=None):
        calls.append(request)
        if pending:
            raise pending.pop(0)
        return FakeResponse(json.dumps(body).encode())

    monkeypatch.setattr(typesafe_client.urllib.request, "urlopen", fake)
    monkeypatch.setattr(typesafe_client.time, "sleep", lambda _: None)
    return calls


def http_error(code, detail=b'{"error": "boom"}'):
    return urllib.error.HTTPError(
        typesafe_client.API_URL, code, "err", {}, io.BytesIO(detail)
    )


def ok_body():
    return {
        "model": "jev-latest",
        "answers": {
            "grade": {"value": "good", "confidence": 0.81},
            "flag": {"probability": 0.12},
        },
        "usage": {"input_tokens": 100},
    }


# --- request envelope -------------------------------------------------------

def test_sends_one_request_with_all_questions(monkeypatch):
    calls = stub_urlopen(monkeypatch, ok_body())
    ask({"symbol": "SPY"}, QUESTIONS, api_key="k")

    assert len(calls) == 1
    sent = json.loads(calls[0].data)
    assert set(sent["questions"]) == set(QUESTIONS)
    assert sent["state"] == {"symbol": "SPY"}
    assert sent["model"] == "jev-latest"


def test_sends_bearer_auth_and_json_content_type(monkeypatch):
    calls = stub_urlopen(monkeypatch, ok_body())
    ask({}, QUESTIONS, api_key="secret-key")

    headers = {k.lower(): v for k, v in calls[0].header_items()}
    assert headers["authorization"] == "Bearer secret-key"
    assert headers["content-type"] == "application/json"


def test_reads_key_from_environment(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-env")
    calls = stub_urlopen(monkeypatch, ok_body())
    ask({}, QUESTIONS)

    headers = {k.lower(): v for k, v in calls[0].header_items()}
    assert headers["authorization"] == "Bearer from-env"


def test_refuses_to_call_without_a_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    calls = stub_urlopen(monkeypatch, ok_body())

    with pytest.raises(TypeSafeError, match="TYPESAFE_API_KEY"):
        ask({}, QUESTIONS)
    assert calls == [], "must not make a request it knows will 401"


# --- errors -----------------------------------------------------------------

def test_401_is_reported_as_a_rejected_key(monkeypatch):
    stub_urlopen(monkeypatch, errors=[http_error(401)])
    with pytest.raises(TypeSafeError, match="key rejected"):
        ask({}, QUESTIONS, api_key="bad")


def test_422_surfaces_the_server_detail(monkeypatch):
    stub_urlopen(monkeypatch, errors=[http_error(422, b"criteria missing")])
    with pytest.raises(TypeSafeError, match="criteria missing"):
        ask({}, QUESTIONS, api_key="k")


def test_401_is_not_retried(monkeypatch):
    calls = stub_urlopen(monkeypatch, errors=[http_error(401), http_error(401)])
    with pytest.raises(TypeSafeError):
        ask({}, QUESTIONS, api_key="bad")
    assert len(calls) == 1, "a bad key will not fix itself"


def test_rate_limit_is_retried_then_succeeds(monkeypatch):
    calls = stub_urlopen(monkeypatch, ok_body(), errors=[http_error(429)])
    answers = ask({}, QUESTIONS, api_key="k")

    assert len(calls) == 2
    assert answers["grade"]["value"] == "good"


def test_gives_up_after_retry_budget(monkeypatch):
    calls = stub_urlopen(monkeypatch, errors=[http_error(529)] * 5)
    with pytest.raises(TypeSafeError):
        ask({}, QUESTIONS, api_key="k")
    assert len(calls) == typesafe_client.RETRIES


def test_missing_answer_is_an_error_not_a_silent_gap(monkeypatch):
    body = ok_body()
    del body["answers"]["flag"]
    stub_urlopen(monkeypatch, body)

    with pytest.raises(TypeSafeError, match="flag"):
        ask({}, QUESTIONS, api_key="k")


def test_response_without_answers_is_an_error(monkeypatch):
    stub_urlopen(monkeypatch, {"model": "jev-latest"})
    with pytest.raises(TypeSafeError, match="answers"):
        ask({}, QUESTIONS, api_key="k")


# --- normalization ----------------------------------------------------------
# The exact field names inside an answer are not pinned down by the reference,
# so the client accepts the plausible spellings and refuses the rest.

@pytest.mark.parametrize("answer", [
    {"probability": 0.3},
    {"value": 0.3},
    {"p": 0.3},
    0.3,
])
def test_noul_probability_is_read_from_known_shapes(answer):
    assert _normalize_answer("q", "noul", answer) == {"probability": 0.3}


def test_score_value_and_confidence(_=None):
    assert _normalize_answer("q", "score", {"value": "good", "confidence": 0.7}) == {
        "value": "good", "confidence": 0.7,
    }


@pytest.mark.parametrize("key", ["value", "choice", "level", "answer", "option"])
def test_choice_value_is_read_from_known_shapes(key):
    got = _normalize_answer("q", "choice", {key: "aligned_bullish"})
    assert got["value"] == "aligned_bullish"


def test_bare_level_is_accepted_with_no_confidence():
    assert _normalize_answer("q", "score", "good") == {
        "value": "good", "confidence": None,
    }


def test_unrecognized_noul_shape_raises_rather_than_guessing():
    with pytest.raises(AnswerShapeError):
        _normalize_answer("flag", "noul", {"unexpected": 0.4})


def test_unrecognized_choice_shape_raises_rather_than_guessing():
    with pytest.raises(AnswerShapeError):
        _normalize_answer("grade", "score", {"unexpected": "good"})


def test_normalized_answers_feed_grade_setup(monkeypatch):
    """The client's output shape is what the grading policy consumes."""
    from typesafe_grade import (
        LOCATION_IS_GOOD, SETUP_QUALITY, SIGNAL_IS_MARGINAL, TREND_AGREEMENT,
        Verdict, grade_setup,
    )

    stub_urlopen(monkeypatch, {
        "model": "jev-latest",
        "answers": {
            SETUP_QUALITY: {"value": "excellent", "confidence": 0.9},
            TREND_AGREEMENT: {"value": "aligned_bullish", "confidence": 0.85},
            SIGNAL_IS_MARGINAL: {"probability": 0.05},
            LOCATION_IS_GOOD: {"probability": 0.88},
        },
    })

    verdict = grade_setup(
        {
            "symbol": "SPY",
            "timeframes": {
                "Daily": {
                    "trend": "BULLISH", "rsi14": 50.0, "bull_signal": True,
                    "bear_signal": False, "in_golden_pocket": True,
                    "last_close": 515.0, "last_high": 515.0, "last_low": 505.0,
                },
            },
            "bull_signal_timeframes": ["Daily"],
        },
        lambda state, questions: ask(state, questions, api_key="k"),
    )

    assert verdict.action == Verdict.TRADEABLE
    assert verdict.grade == "excellent"
