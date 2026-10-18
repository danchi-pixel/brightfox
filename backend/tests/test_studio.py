"""Topics: approval per learner and version, the kid's space, practice runs, the study part, results."""
from __future__ import annotations

from sqlalchemy import update

from app.db import SessionLocal
from app.models import ContentAccess

from .conftest import Fam

PRIMER = "2026-10-17-primer-ulomki"
PEOPLE = "2026-10-17-erik-english-people"


def test_family_sees_global_and_own_topics(fam_a: Fam, dan: Fam):
    a_ids = {t["id"] for t in fam_a.admin.get("/api/studio/topics").json()["topics"]}
    assert a_ids == {PRIMER}
    d = {t["id"]: t for t in dan.admin.get("/api/studio/topics").json()["topics"]}
    assert {PRIMER, PEOPLE} <= set(d) and d[PEOPLE]["scope"] == "family" and d[PRIMER]["scope"] == "global"
    assert d[PEOPLE]["for"] == ["Erik"] and d[PEOPLE]["cards"] == 38 and not d[PEOPLE]["approved"]
    assert fam_a.admin.get(f"/api/studio/topics/{PEOPLE}").status_code == 404  # another family's topic


def test_approval_per_learner_and_version(dan: Fam, fam_b: Fam):
    a = dan.admin
    v = a.get(f"/api/studio/topics/{PEOPLE}").json()["version"]
    assert a.put(f"/api/studio/topics/{PEOPLE}/access", json={"version": v - 1, "learner_ids": [dan.learners["Erik"]]}).status_code == 409
    assert a.put(f"/api/studio/topics/{PEOPLE}/access", json={"version": v, "learner_ids": [fam_b.learners["Cene"]]}).status_code == 404
    r = a.put(f"/api/studio/topics/{PEOPLE}/access", json={"version": v, "learner_ids": [dan.learners["Erik"]]}).json()
    assert r == {"learner_ids": [dan.learners["Erik"]], "outdated_ids": [], "approved": True}
    erik, alan = dan.kids["Erik"], dan.kids["Alan"]
    assert [t["id"] for t in erik.get(f"/api/learners/{dan.learners['Erik']}/home").json()["topics"]] == [PEOPLE]
    assert alan.get(f"/api/learners/{dan.learners['Alan']}/home").json()["topics"] == []
    assert alan.get(f"/api/learners/{dan.learners['Alan']}/topics/{PEOPLE}").status_code == 404
    assert erik.get(f"/api/learners/{dan.learners['Erik']}/topics/{PEOPLE}").json()["id"] == PEOPLE
    # The parent previews the kid's space (same data, flagged as not the owner).
    home = a.get(f"/api/learners/{dan.learners['Erik']}/home").json()
    assert home["owner"] is False and [t["id"] for t in home["topics"]] == [PEOPLE]

    # A changed file (older approval) hides the topic until the parent checks it again.
    with SessionLocal() as db:
        db.execute(update(ContentAccess).where(ContentAccess.content_id == PEOPLE).values(version=v - 1))
        db.commit()
    assert erik.get(f"/api/learners/{dan.learners['Erik']}/home").json()["topics"] == []
    t = a.get(f"/api/studio/topics/{PEOPLE}").json()
    assert t["learner_ids"] == [] and t["outdated_ids"] == [dan.learners["Erik"]] and not t["approved"]
    a.put(f"/api/studio/topics/{PEOPLE}/access", json={"version": v, "learner_ids": [dan.learners["Erik"]]})


def test_runs_challenge_and_results(dan: Fam):
    lid = dan.learners["Erik"]
    erik, parent = dan.kids["Erik"], dan.admin
    topic = erik.get(f"/api/learners/{lid}/topics/{PEOPLE}").json()
    first, second = topic["tasks"][0]["id"], topic["tasks"][1]["id"]
    url = f"/api/learners/{lid}/topics/{PEOPLE}/runs"
    body = {"results": {first: {"first": True, "tries": 1}, second: {"first": False, "tries": 2, "wrong": ["Spainish"]}},
            "finished": False}
    assert parent.post(url, json=body).status_code == 403  # a parent's preview is never saved
    assert erik.post(url, json={"results": {"nope": {}}}).status_code == 400
    assert erik.post(url, json={"results": {}, "challenge": True}).status_code == 409  # locked until practice is finished
    assert erik.post(url, json=body).status_code == 201
    assert erik.post(url, json={**body, "finished": True}).status_code == 201
    ch = topic["challenge"][0]["id"]
    assert erik.post(url, json={"results": {ch: {"first": True}}, "finished": True, "challenge": True}).status_code == 201

    card = next(t for t in erik.get(f"/api/learners/{lid}/home").json()["topics"] if t["id"] == PEOPLE)
    assert card["runs"] == 2 and card["finished"] == 1
    assert card["challenge_state"] == {"tasks": len(topic["challenge"]), "unlocked": True, "cleared": True}

    res = parent.get(f"/api/studio/topics/{PEOPLE}/results").json()["learners"]
    me = next(r for r in res if r["learner"]["id"] == lid)
    assert me["latest"]["finished"] and me["latest"]["first"] == 1
    assert me["latest"]["tricky"] == [{"id": second, "wrong": ["Spainish"], "shown": False, "hints": 0}]
    assert me["tasks"][second]["wrong"] == ["Spainish"] and me["tasks"][second]["seen"] == 2
    assert me["challenge"]["latest"]["first"] == 1
    # Task rows carry level and kind from the topic, so mastery can be computed later.
    with SessionLocal() as db:
        from app.models import TaskResult
        row = db.query(TaskResult).filter(TaskResult.learner_id == lid, TaskResult.task_id == second).first()
        assert row.level == topic["tasks"][1]["level"] and row.kind == topic["tasks"][1]["kind"]


def test_study_progress_by_goal_id(dan: Fam):
    lid = dan.learners["Erik"]
    erik = dan.kids["Erik"]
    url = f"/api/learners/{lid}/topics/{PEOPLE}/progress"
    topic = erik.get(f"/api/learners/{lid}/topics/{PEOPLE}").json()
    back = topic["study"]["cards"][0]["back"]
    assert dan.admin.put(url, json={"known": [back]}).status_code == 403
    assert erik.put(url, json={"goals": ["g99"]}).status_code == 400
    st = erik.put(url, json={"known": [back, back], "goals": ["g1", "g0"]}).json()
    assert st["known"] == [back] and st["ticked"] == ["g0", "g1"] and st["goal_ids"][0] == "g0"
    card = next(t for t in erik.get(f"/api/learners/{lid}/home").json()["topics"] if t["id"] == PEOPLE)
    assert card["study_state"]["known"] == [back]
    res = dan.admin.get(f"/api/studio/topics/{PEOPLE}/results").json()["learners"]
    assert next(r for r in res if r["learner"]["id"] == lid)["study"]["ticked"] == ["g0", "g1"]


def test_unapprove(dan: Fam):
    lid = dan.learners["Erik"]
    assert dan.admin.delete(f"/api/studio/topics/{PEOPLE}/access").json()["learner_ids"] == []
    assert dan.kids["Erik"].get(f"/api/learners/{lid}/topics/{PEOPLE}").status_code == 404
