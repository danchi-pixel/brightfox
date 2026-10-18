"""The typed oral exam with a fake AI provider (the real API is never called in tests)."""
from __future__ import annotations

import pytest

from app import llm
from app.llm import service as llm_service
from app.oral.grading import parse

from .conftest import Fam

PEOPLE = "2026-10-17-erik-english-people"
PRIMER = "2026-10-17-primer-ulomki"


class Grader:
    def __init__(self) -> None:
        self.requests: list[llm.LLMRequest] = []
        self.text = '{"verdict": "partly", "feedback": "Dobro! Dodaj še narodnost: He\'s French."}'

    def __call__(self, req, spec, effort):
        self.requests.append(req)
        return llm.LLMReply(text=self.text, model=spec.id, provider="fake", refused=False, cut_off=False, cost_usd=0.002)


@pytest.fixture()
def grader():
    g = Grader()
    llm_service.set_test_provider(g)
    yield g
    llm_service.set_test_provider(None)


def test_parse():
    assert parse('Sure: {"verdict": "right", "feedback": "Odlično!"}') == ("right", "Odlično!")
    assert parse('{"verdict": "maybe", "feedback": "x"}') == ("partly", '{"verdict": "maybe", "feedback": "x"}')
    assert parse("Not JSON at all") == ("partly", "Not JSON at all")


def test_oral_flow(dan: Fam, grader: Grader):
    lid = dan.learners["Alan"]
    a, kid = dan.admin, dan.kids["Alan"]
    v = a.get(f"/api/studio/topics/{PEOPLE}").json()["version"]
    a.put(f"/api/studio/topics/{PEOPLE}/access", json={"version": v, "learner_ids": [lid]})
    a.patch(f"/api/family/learners/{lid}", json={"tutor_daily_limit": 2})
    card = next(t for t in kid.get(f"/api/learners/{lid}/home").json()["topics"] if t["id"] == PEOPLE)
    assert card["oral"] == 5

    assert a.post(f"/api/learners/{lid}/oral", json={"topic_id": PEOPLE}).status_code == 403  # a parent only previews
    s = kid.post(f"/api/learners/{lid}/oral", json={"topic_id": PEOPLE}).json()
    assert [q["id"] for q in s["questions"]][0] == "o-nationality" and s["turns"] == []
    url = f"/api/learners/{lid}/oral/{s['id']}/answers"
    assert kid.post(url, json={"question_id": "nope", "answer": "x"}).status_code == 400
    r = kid.post(url, json={"question_id": "o-nationality", "answer": "He is from France."}).json()
    assert r["verdict"] == "partly" and "French" in r["feedback"] and r["model_answer"].startswith("He's from France") and r["left_today"] == 1
    req = grader.requests[-1]
    assert req.job == "oral_grading" and "He is from France." in req.turns[0].text and "Key points" in req.turns[0].text

    grader.text = '{"verdict": "right", "feedback": "Odlično!"}'
    assert kid.post(url, json={"question_id": "o-family", "answer": "There are four people in my family."}).json()["verdict"] == "right"
    # Oral answers count toward Foxy's daily limit.
    assert kid.post(url, json={"question_id": "o-can", "answer": "I can swim."}).status_code == 429

    past = a.get(f"/api/learners/{lid}/oral").json()
    assert past[0]["turns"][0]["answer"] == "He is from France." and past[0]["turns"][1]["verdict"] == "right"
    a.delete(f"/api/studio/topics/{PEOPLE}/access")


def test_topic_without_oral(fam_a: Fam, grader: Grader):
    lid = fam_a.learners["Ana"]
    v = fam_a.admin.get(f"/api/studio/topics/{PRIMER}").json()["version"]
    fam_a.admin.put(f"/api/studio/topics/{PRIMER}/access", json={"version": v, "learner_ids": [lid]})
    assert fam_a.kids["Ana"].post(f"/api/learners/{lid}/oral", json={"topic_id": PRIMER}).status_code == 404
