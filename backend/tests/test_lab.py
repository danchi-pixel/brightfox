from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from app.config import settings
from app.content.lab import Lab
from app.content.registry import content
from app.db import SessionLocal
from app.models import LabProgress, LabActivation

TID = "2026-10-28-erik-naravoslovje"


@pytest.fixture
def lab(dan, monkeypatch):
    monkeypatch.setattr(settings, "local_family", "danijel")
    lid = dan.learners["Erik"]
    with SessionLocal() as db:
        db.execute(delete(LabProgress).where(LabProgress.learner_id == lid, LabProgress.topic_id == TID))
        db.execute(delete(LabActivation).where(LabActivation.learner_id == lid, LabActivation.topic_id == TID))
        db.commit()
    return dan.kids["Erik"], f"/api/learners/{lid}/topics/{TID}/lab", dan


def body(revision=0, index=0, rating=None, mode="oral"):
    return {"revision": revision, "version": content().topics[TID]["version"],
        "session": {"mode": mode, "queue": ["sonce-planet", "dan-noc"], "index": index,
                    "ratings": {"sonce-planet": rating} if rating else {}},
        **({"question": "sonce-planet", "rating": rating} if rating else {})}


def test_save_resume_and_spaced_recall(lab):
    kid, base, _ = lab
    assert kid.get(base + "/progress").json()["revision"] == 0
    assert kid.put(base + "/progress", json=body()).status_code == 200
    first = kid.put(base + "/progress", json=body(1, 1, "know", "cards")).json()
    assert first["answers"]["cards:sonce-planet"]["interval"] == 1
    assert kid.get(base + "/progress").json()["session"]["index"] == 1
    second = kid.put(base + "/progress", json=body(2, 1, "know", "cards")).json()
    assert second["answers"]["cards:sonce-planet"]["interval"] == 2
    third = kid.put(base + "/progress", json=body(3, 1, "again", "cards")).json()
    assert third["answers"]["cards:sonce-planet"]["interval"] == 0
    assert third["answers"]["cards:sonce-planet"]["attempts"] == 3
    assert "practice:sonce-planet" not in third["answers"]


def test_stale_retry_does_not_duplicate_attempt(lab):
    kid, base, _ = lab
    assert kid.put(base + "/progress", json=body(0, 1, "practice")).status_code == 200
    assert kid.put(base + "/progress", json=body(0, 1, "practice")).status_code == 409
    state = kid.get(base + "/progress").json()
    assert state["answers"]["practice:sonce-planet"]["attempts"] == 1


def test_scope_parent_preview_and_private_images(lab, fam_b, tmp_path, monkeypatch):
    kid, base, dan = lab
    source = content().topics[TID]["lab"]["sources"][0]
    # Only synthetic bytes are written to the scratch data folder.
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    folder = settings.files_dir / "study" / "danijel" / TID
    folder.mkdir(parents=True)
    (folder / source["file"]).write_bytes(b"scratch jpeg")
    result = kid.get(base + "/images/p01")
    assert result.status_code == 200 and result.content == b"scratch jpeg"
    assert result.headers["cache-control"] == "private, no-store"
    assert kid.get(base + "/images/unknown").status_code == 404
    assert fam_b.admin.get(base + "/images/p01").status_code == 404
    assert dan.kids["Alan"].get(base + "/images/p01").status_code == 404
    assert dan.admin.get(base + "/progress").status_code == 200
    assert dan.admin.put(base + "/progress", json=body()).status_code == 403
    own_alan = base.replace(str(dan.learners["Erik"]), str(dan.learners["Alan"]), 1)
    assert dan.kids["Alan"].get(own_alan + "/progress").status_code == 404


def test_approval_and_input_validation(lab, monkeypatch):
    kid, base, _ = lab
    bad = body(); bad["session"]["queue"] = ["unknown"]
    assert kid.put(base + "/progress", json=bad).status_code == 400
    bad = body(); bad["version"] = 999
    assert kid.put(base + "/progress", json=bad).status_code == 409
    monkeypatch.setattr(settings, "local_family", None)
    assert kid.get(base + "/progress").status_code == 404
    assert kid.get(base + "/images/p01").status_code == 404


def test_bank_coverage_and_validation():
    bank = deepcopy(content().topics[TID]["lab"])
    assert len(bank["sources"]) == 38
    parsed = Lab.model_validate(bank)
    for lesson in parsed.lessons:
        qs = [q for q in parsed.questions if q.topic == lesson.id]
        assert any(q.kind == "oral" for q in qs)
        assert any(q.kind != "oral" for q in qs)
        assert any(q.card for q in qs)
    assert {s.id for s in parsed.sources} <= {sid for l in parsed.lessons for sid in l.sources}
    bank["questions"][0]["sources"] = ["missing"]
    with pytest.raises(ValidationError): Lab.model_validate(bank)


def test_default_sources_and_parent_activation_preserve_progress(lab, fam_b):
    kid, base, dan = lab
    initial = kid.get(base + "/availability").json()
    assert len(initial["active_questions"]) == 25
    assert initial["enabled_lessons"] == [] and not initial["can_manage"]
    assert initial["question_groups"]["toplotni-poskus"] == "review"
    assert initial["question_groups"]["zemlja-plasti"] == "textbook"
    payload = {"version": content().topics[TID]["version"], "enabled": True}
    url = base + "/availability/materiali"
    assert kid.put(url, json=payload).status_code == 403
    assert fam_b.admin.put(url, json=payload).status_code == 404
    inactive = body(); inactive["session"]["queue"] = ["material-izbira"]
    assert kid.put(base + "/progress", json=inactive).status_code == 409
    assert kid.get(base + "/progress").json()["revision"] == 0
    enabled = dan.admin.put(url, json=payload)
    assert enabled.status_code == 200
    assert len(enabled.json()["active_questions"]) == 31
    assert "toplotni-poskus" not in enabled.json()["active_questions"]
    inactive.update(question="material-izbira", rating="know")
    assert kid.put(base + "/progress", json=inactive).status_code == 200
    saved = kid.get(base + "/progress").json()
    assert dan.admin.put(url, json={**payload, "enabled": False}).status_code == 200
    assert kid.get(base + "/progress").json() == saved
    inactive["revision"] = saved["revision"]
    assert kid.put(base + "/progress", json=inactive).status_code == 409
    assert dan.admin.put(url, json=payload).status_code == 200
    assert kid.get(base + "/progress").json() == saved
    assert dan.admin.put(base + "/availability/unknown", json=payload).status_code == 400
    assert dan.admin.put(url, json={**payload, "version": 999}).status_code == 409


def test_legacy_paths_readiness_and_saved_cards_follow_activation(lab):
    from app.models import TopicProgress
    kid, base, dan = lab
    topic_url = base.removesuffix("/lab")
    learner_url = topic_url.split("/topics/")[0]
    topic = kid.get(topic_url).json()
    assert {t["id"] for t in topic["tasks"]} == {"uvod-5", "uvod-6", "uvod-9", "uvod-10"}
    assert len(topic["lab"]["questions"]) == 99  # full read-only catalog remains accessible
    assert topic["study"]["cards"] == []
    before = kid.get(learner_url + "/mastery").json()
    m = next(t for t in before["topics"] if t["topic_id"] == TID)
    assert m["skills"][0]["parts"]["practice"]["total"] == 4
    assert kid.post(topic_url + "/runs", json={"results": {"uvod-1": {"got_it": True}}}).status_code == 400
    with SessionLocal() as db:
        p = db.get(TopicProgress, (dan.learners["Erik"], TID))
        if not p:
            p = TopicProgress(family_id=dan.id, learner_id=dan.learners["Erik"], topic_id=TID)
            db.add(p)
        p.known = ["prevajanje toplote"]; p.goals = []
        db.commit()
    assert kid.put(topic_url + "/progress", json={"known": [], "goals": []}).status_code == 200
    with SessionLocal() as db:
        assert db.get(TopicProgress, (dan.learners["Erik"], TID)).known == ["prevajanje toplote"]
    payload = {"version": content().topics[TID]["version"], "enabled": True}
    assert dan.admin.put(base + "/availability/materiali", json=payload).status_code == 200
    assert len(kid.get(topic_url).json()["tasks"]) == 5
    h = kid.get(learner_url + "/home").json()
    card = next(t for t in h["topics"] if t["id"] == TID)
    assert card["study_state"]["known"] == ["prevajanje toplote"]


def test_mixed_and_unknown_sources_fail_closed(lab):
    from app.learning.lab_scope import source_group
    bank = content().topics[TID]["lab"]
    assert source_group(bank, ["p01", "p16"]) == "review"
    assert source_group(bank, ["missing"]) == "review"
    assert source_group(bank, []) == "review"
    kid, base, dan = lab
    payload = {"version": content().topics[TID]["version"], "enabled": True}
    assert dan.admin.put(base + "/availability/toplota", json=payload).status_code == 200
    scope = kid.get(base + "/availability").json()
    assert "toplotni-poskus" not in scope["active_questions"]
    invalid = body(); invalid["session"]["queue"] = ["toplotni-poskus"]
    assert kid.put(base + "/progress", json=invalid).status_code == 409


def test_inactive_mistakes_do_not_enter_review_or_its_counts(lab):
    from datetime import timedelta
    from app.models import ReviewItem
    from app.timeutil import local_today
    from sqlalchemy import select
    kid, base, dan = lab
    learner_url = base.split("/topics/")[0]
    with SessionLocal() as db:
        rows = [ReviewItem(family_id=dan.id, learner_id=dan.learners["Erik"], topic_id=TID,
                 item_kind="task", item_id=task, box=1, due_date=local_today("Europe/Ljubljana") - timedelta(days=5))
                for task in ["uvod-1", "uvod-5"]]
        db.add_all(rows); db.commit()
        ids = [r.id for r in rows]
    review = kid.get(learner_url + "/review").json()
    assert ids[0] not in {r["id"] for r in review["items"]}
    assert ids[1] in {r["id"] for r in review["items"]}
    count = review["open"]
    payload = {"version": content().topics[TID]["version"], "enabled": True}
    assert dan.admin.put(base + "/availability/materiali", json=payload).status_code == 200
    review = kid.get(learner_url + "/review").json()
    assert ids[0] in {r["id"] for r in review["items"]}
    assert review["open"] == count + 1
    with SessionLocal() as db:
        assert len(list(db.scalars(select(ReviewItem).where(ReviewItem.id.in_(ids))))) == 2
