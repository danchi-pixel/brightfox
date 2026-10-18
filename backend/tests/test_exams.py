"""Tests at school, the plan, mastery, gaps and Moje napake through the API."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from .conftest import Fam, make_family

PRIMER = "2026-10-17-primer-ulomki"


@pytest.fixture(scope="module")
def fam(client) -> Fam:
    f = make_family("fam-exam", ["Nika", "Oto"])
    v = f.admin.get(f"/api/studio/topics/{PRIMER}").json()["version"]
    f.admin.put(f"/api/studio/topics/{PRIMER}/access", json={"version": v, "learner_ids": [f.learners["Nika"]]})
    return f


def _exam_body(days: int = 5, **kw):
    return {"subject": "math", "title": "Test iz ulomkov", "exam_date": (date.today() + timedelta(days=days)).isoformat(),
            "target_grade": 5, "scope": [{"topic_id": PRIMER}], **kw}


def test_parent_enters_a_test_kid_sees_it(fam: Fam):
    lid = fam.learners["Nika"]
    kid = fam.kids["Nika"]
    assert kid.post(f"/api/learners/{lid}/exams", json=_exam_body()).status_code == 403
    assert fam.admin.post(f"/api/learners/{lid}/exams", json=_exam_body(scope=[{"topic_id": "2026-10-17-erik-english-people"}])).status_code == 400
    assert fam.admin.post(f"/api/learners/{fam.learners['Oto']}/exams", json=_exam_body()).status_code == 400  # not approved for Oto
    e = fam.admin.post(f"/api/learners/{lid}/exams", json=_exam_body()).json()
    assert e["days_left"] == 5 and e["readiness"] is None and e["scope"][0]["topic_title"]
    listed = kid.get(f"/api/learners/{lid}/exams").json()
    assert [x["id"] for x in listed] == [e["id"]]
    detail = kid.get(f"/api/learners/{lid}/exams/{e['id']}").json()
    days = detail["plan"]["days"]
    assert days and days[0]["steps"] and days[0]["steps"][0]["kind"] in ("learn", "practice")
    assert fam.kids["Oto"].get(f"/api/learners/{lid}/exams").status_code == 404


def test_practice_moves_readiness_and_fills_moje_napake(fam: Fam):
    lid = fam.learners["Nika"]
    kid = fam.kids["Nika"]
    topic = kid.get(f"/api/learners/{lid}/topics/{PRIMER}").json()
    ids = [t["id"] for t in topic["tasks"]]
    results = {i: {"first": True, "tries": 1} for i in ids[:6]}
    results[ids[1]] = {"first": False, "tries": 2, "wrong": ["1/5"]}
    assert kid.post(f"/api/learners/{lid}/topics/{PRIMER}/runs", json={"results": results, "finished": True}).status_code == 201

    m = kid.get(f"/api/learners/{lid}/mastery").json()["topics"][0]
    assert m["skills"][0]["skill_id"] == "_topic" and m["skills"][0]["parts"]["practice"] == {"done": 5.0, "total": 10}
    e = kid.get(f"/api/learners/{lid}/exams").json()[0]
    assert e["readiness"] == 0.5  # 5 of 10 practice tasks right first time

    # The task that needed help is due tomorrow, not today.
    r = kid.get(f"/api/learners/{lid}/review").json()
    assert r["items"] == [] and r["open"] == 1
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = kid.get(f"/api/learners/{lid}/review?today={tomorrow}").json()
    assert [i["task"]["id"] for i in r["items"]] == [ids[1]] and r["items"][0]["wrong"] == "1/5"

    item = r["items"][0]["id"]
    assert fam.admin.post(f"/api/learners/{lid}/review/answers", json={"results": {str(item): {"first": True}}}).status_code == 403
    out = kid.post(f"/api/learners/{lid}/review/answers", json={"results": {str(item): {"first": True, "tries": 1}}, "today": tomorrow}).json()
    assert out == {"answered": 1, "cleared": 0}
    # Answered right: the latest result of that task is now good, so readiness went up.
    assert kid.get(f"/api/learners/{lid}/exams?today={tomorrow}").json()[0]["readiness"] == 0.6
    assert kid.get(f"/api/learners/{lid}/review?today={tomorrow}").json()["items"] == []


def test_gaps_week_and_trophies(fam: Fam):
    lid = fam.learners["Nika"]
    kid = fam.kids["Nika"]
    g = kid.get(f"/api/learners/{lid}/gaps").json()["gaps"]
    # On the test in 5 days at about 60 %: worth attention (not critical, which is below 50 %).
    assert any(x["severity"] == "attention" and x["topic_id"] == PRIMER and "60 %" in x["reasons"][0] for x in g)
    w = kid.get(f"/api/learners/{lid}/week").json()
    assert len(w["days"]) == 7 and any(d["active"] for d in w["days"]) and sum(d["today"] for d in w["days"]) == 1
    assert w["trophies"] == {"cups": 0, "corrected": 0}


def test_parent_edits_and_deletes(fam: Fam):
    lid = fam.learners["Nika"]
    e = fam.admin.get(f"/api/learners/{lid}/exams").json()[0]
    upd = fam.admin.put(f"/api/learners/{lid}/exams/{e['id']}", json=_exam_body(days=2, title="Ulomki 2", notes="Str. 34–40")).json()
    assert upd["title"] == "Ulomki 2" and upd["days_left"] == 2 and upd["notes"] == "Str. 34–40"
    assert fam.kids["Nika"].delete(f"/api/learners/{lid}/exams/{e['id']}").status_code == 403
    assert fam.admin.delete(f"/api/learners/{lid}/exams/{e['id']}").json() == {"deleted": e["id"]}
    assert fam.admin.get(f"/api/learners/{lid}/exams").json() == []
