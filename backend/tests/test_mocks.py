"""Mock tests: approval per learner, a timed run with points, the parent's grade estimate, mastery and the plan."""
from __future__ import annotations

from datetime import date, timedelta

from .conftest import Fam

PEOPLE = "2026-10-17-erik-english-people"
MOCK = "2026-10-18-erik-english-people-mock"


def test_mock_flow(dan: Fam, fam_a: Fam):
    lid = dan.learners["Mia"]
    a, kid = dan.admin, dan.kids["Mia"]
    card = next(m for m in a.get("/api/studio/mocks").json()["mocks"] if m["id"] == MOCK)
    assert card["points"] == 28 and card["minutes"] == 30 and not card["approved"] and card["for"] == ["Erik"]
    assert fam_a.admin.get(f"/api/studio/mocks/{MOCK}").status_code == 404  # another family's mock
    assert kid.get(f"/api/learners/{lid}/mocks/{MOCK}").status_code == 404  # not approved yet
    assert a.put(f"/api/studio/mocks/{MOCK}/access", json={"version": card["version"], "learner_ids": [lid]}).json()["approved"]

    m = kid.get(f"/api/learners/{lid}/mocks/{MOCK}").json()
    assert "scale" not in m and len([t for s in m["sections"] for t in s["tasks"]]) == 17
    answers = {"m-uncle": {"right": True}, "m-cousin": {"right": True}, "m-spanish": {"right": False, "given": "Spain"},
               "m-we-havent": {"right": True}, "m-write": {"got_it": True}, "m-listen": {"right": True}}
    assert a.post(f"/api/learners/{lid}/mocks/{MOCK}/runs", json={"answers": answers, "minutes_used": 20}).status_code == 403
    assert kid.post(f"/api/learners/{lid}/mocks/{MOCK}/runs", json={"answers": {"nope": {}}, "minutes_used": 1}).status_code == 400
    res = kid.post(f"/api/learners/{lid}/mocks/{MOCK}/runs", json={"answers": answers, "minutes_used": 24}).json()
    assert res["points"] == 1 + 1 + 2 + 5 + 3 and res["max"] == 28 and "grade_estimate" not in res  # kids never see a grade
    assert any(x["id"] == "m-spanish" and x["wrong"] == ["Spain"] for x in res["missed"])

    mine = next(r for r in a.get(f"/api/studio/mocks/{MOCK}").json()["results"] if r["learner"]["id"] == lid)
    assert mine["pct"] == 43 and mine["grade_estimate"] == 1 and mine["minutes_used"] == 24

    # Mock points feed mastery (once the topic is approved) and the plan puts the mock before the test.
    v = a.get(f"/api/studio/topics/{PEOPLE}").json()["version"]
    a.put(f"/api/studio/topics/{PEOPLE}/access", json={"version": v, "learner_ids": [lid]})
    topic = next(t for t in kid.get(f"/api/learners/{lid}/mastery").json()["topics"] if t["topic_id"] == PEOPLE)
    fam_skill = next(s for s in topic["skills"] if s["skill_id"] == "fam")
    assert fam_skill["parts"]["mock"] == {"done": 1.0, "total": 1} and fam_skill["mastery"] is not None
    exam = a.post(f"/api/learners/{lid}/exams", json={"subject": "english", "title": "Unit 1",
                                                       "exam_date": (date.today() + timedelta(days=6)).isoformat(),
                                                       "scope": [{"topic_id": PEOPLE}]}).json()
    plan = kid.get(f"/api/learners/{lid}/exams/{exam['id']}").json()["plan"]
    mock_steps = [s for day in plan["days"] for s in day["steps"] if s["kind"] == "mock"]
    assert len(mock_steps) == 1 and mock_steps[0]["topic_id"] == MOCK
    assert kid.get(f"/api/learners/{lid}/mocks").json()[0]["last"]["points"] == 12

    # Leave the shared scratch family as it was for the topic tests.
    a.delete(f"/api/learners/{lid}/exams/{exam['id']}")
    a.delete(f"/api/studio/topics/{PEOPLE}/access")
    a.delete(f"/api/studio/mocks/{MOCK}/access")
