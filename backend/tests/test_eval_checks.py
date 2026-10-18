"""The eval's automatic checks and its cost estimate (no API calls)."""
from __future__ import annotations

from evals.checks import run_checks
from evals.run_eval import estimate, load_cases, request_for

CASE = {"id": "x", "grade": 4, "subject": "math", "language": "sl", "answer": "6",
        "turns": [{"role": "user", "text": "Koliko je 3/4 od 8?"}], "expect": ""}


def test_good_reply_passes_every_check():
    r = run_checks(CASE, "Dobro vprašanje! Na koliko enakih delov razdelimo 8, če iščemo četrtine?")
    assert all(ok for ok, _ in r.values()), r


def test_bad_reply_is_caught():
    r = run_checks(CASE, "The answer is 6. Si naredil prav? 6.5 is close.")
    assert not r["no_answer_first"][0] and not r["gender_neutral"][0] and not r["decimal_comma"][0]
    assert not r["language"][0]


def test_cases_load_and_estimate_is_small():
    cases = load_cases("tutor_chat")
    assert len(cases) >= 12 and all(request_for(c).turns for c in cases)
    est = estimate(cases, ["claude-opus-5-5", "claude-haiku-5-5"], 2)
    assert 0 < est < 5
