"""
TYPESAFE HTTP CLIENT
--------------------
The transport `typesafe_grade.grade_setup()` expects as its `ask` argument:
sends the assembled state and question set to the TypeSafe System One API and
normalizes the answers into the shape the grading policy consumes.

Contract (per the TypeSafe agent skill's API reference):

    POST https://api.typesafe.ai/v1/systemone
    Authorization: Bearer <API_KEY>
    Content-Type: application/json

    request:  {"state": ..., "model": "jev-latest", "questions": {...}}
    response: {"model": ..., "answers": {<question_id>: ...}, "usage": {...}}

    Choice and Score answers carry a confidence in 0..1; a Noul answers with the
    probability that the condition holds and has no separate confidence.
    Errors: 401 invalid key, 422 validation failure, 429/529 rate limited.

!! UNVERIFIED AGAINST THE LIVE API !!
This module has never made a real call. The endpoint, auth header, request
envelope and error codes come from the documented reference above, but the
exact field names *inside* each answer object are not pinned down by it, so
_normalize_answer() accepts the plausible spellings and raises a loud error
rather than guessing when it sees something else. Before this is trusted with
sizing decisions, run scripts/typesafe_smoke.py with a real key and reconcile
_normalize_answer() with what actually comes back.

The API key is read from the TYPESAFE_API_KEY environment variable and is never
logged or echoed. Keep it server-side.
"""

import json
import os
import time
import urllib.error
import urllib.request

API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
DEFAULT_TIMEOUT = 30

# Rate limits and transient upstream failures are worth retrying; a bad key or a
# malformed question is not, and retrying either just burns time.
RETRY_STATUSES = (429, 529)
RETRIES = 3
BACKOFF_SECONDS = 2


class TypeSafeError(RuntimeError):
    """Any failure to obtain usable answers from the API."""


class AnswerShapeError(TypeSafeError):
    """The response parsed as JSON but an answer did not match any known shape.

    Raised instead of guessing: a misread probability would silently corrupt the
    veto in typesafe_grade, which is exactly the kind of failure that must not
    reach a sizing decision quietly.
    """


def ask(state, questions, api_key=None, model=DEFAULT_MODEL, timeout=DEFAULT_TIMEOUT,
        url=API_URL):
    """Send one request carrying every question, and return
    {question_id: normalized_answer}.

    All questions go in a single request: they are independent judgments over
    the same state, so they run in parallel server-side.
    """
    api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise TypeSafeError(
            "TYPESAFE_API_KEY is not set; refusing to call the API without a key"
        )

    payload = json.dumps(
        {"state": state, "model": model, "questions": questions}
    ).encode("utf-8")

    body = _post(url, payload, api_key, timeout)

    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise TypeSafeError(f"response had no 'answers' object (keys: {sorted(body)})")

    missing = set(questions) - set(answers)
    if missing:
        raise TypeSafeError(f"no answer returned for: {sorted(missing)}")

    return {
        qid: _normalize_answer(qid, questions[qid].get("type"), answers[qid])
        for qid in questions
    }


def _post(url, payload, api_key, timeout):
    """POST with backoff on rate limiting. Returns the decoded JSON body."""
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    last_error = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Read the body once: it usually carries the reason a 422 rejected
            # a question, which is the single most useful thing when debugging.
            detail = _safe_detail(exc)
            if exc.code in RETRY_STATUSES and attempt < RETRIES - 1:
                last_error = exc
                time.sleep(BACKOFF_SECONDS * (2 ** attempt))
                continue
            if exc.code == 401:
                raise TypeSafeError("401: API key rejected") from exc
            if exc.code == 422:
                raise TypeSafeError(f"422: request rejected -- {detail}") from exc
            raise TypeSafeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < RETRIES - 1:
                last_error = exc
                time.sleep(BACKOFF_SECONDS * (2 ** attempt))
                continue
            raise TypeSafeError(f"could not reach {url}: {exc.reason}") from exc

    raise TypeSafeError(f"giving up after {RETRIES} attempts: {last_error}")


def _normalize_answer(qid, qtype, answer):
    """Reduce an answer object to what typesafe_grade consumes:
    {"value": str, "confidence": float} for choice/score,
    {"probability": float} for noul.

    A bare scalar is accepted (a probability for a noul, a level name
    otherwise), since that is a plausible compact form. Anything else raises,
    rather than defaulting to a value that would quietly change a verdict.
    """
    if qtype == "noul":
        probability = _extract(answer, ("probability", "value", "p", "yes"))
        if probability is None:
            raise AnswerShapeError(
                f"{qid}: no probability found in noul answer {answer!r}"
            )
        return {"probability": float(probability)}

    # choice / score
    if not isinstance(answer, dict):
        # A bare level or option name, with no distribution to read.
        return {"value": answer, "confidence": None}

    value = _extract(answer, ("value", "choice", "level", "answer", "option"))
    if value is None:
        raise AnswerShapeError(f"{qid}: no value found in answer {answer!r}")

    confidence = _extract(answer, ("confidence",))
    return {
        "value": value,
        "confidence": None if confidence is None else float(confidence),
    }


def _extract(answer, keys):
    """First present key from `keys`, or the answer itself if it is a scalar."""
    if not isinstance(answer, dict):
        return answer
    for key in keys:
        if key in answer and answer[key] is not None:
            return answer[key]
    return None


def _safe_detail(exc):
    """The error body as text, for the exception message. Never raises: a
    failure to read the explanation must not replace the original error."""
    try:
        detail = exc.read().decode("utf-8", "replace").strip()
    except Exception:
        return "<no response body>"
    return detail[:500] or "<empty response body>"
