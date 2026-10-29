from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from app.config import settings
from app.content.lab import Lab
from app.content.registry import content
from app.db import SessionLocal
from app.models import LabProgress

TID = "2026-10-28-erik-naravoslovje"


@pytest.fixture
def lab(dan, monkeypatch):
    monkeypatch.setattr(settings, "local_family", "danijel")
    lid = dan.learners["Erik"]
    with SessionLocal() as db:
        db.execute(delete(LabProgress).where(LabProgress.learner_id == lid, LabProgress.topic_id == TID))
        db.commit()
    return dan.kids["Erik"], f"/api/learners/{lid}/topics/{TID}/lab", dan


def body(revision=0, index=0, rating=None, mode="oral"):
    return {"revision": revision, "version": content().topics[TID]["version"],
        "session": {"mode": mode, "queue": ["material-izbira", "magnet"], "index": index,
                    "ratings": {"material-izbira": rating} if rating else {}},
        **({"question": "material-izbira", "rating": rating} if rating else {})}


def test_save_resume_and_spaced_recall(lab):
    kid, base, _ = lab
    assert kid.get(base + "/progress").json()["revision"] == 0
    assert kid.put(base + "/progress", json=body()).status_code == 200
    first = kid.put(base + "/progress", json=body(1, 1, "know", "cards")).json()
    assert first["answers"]["cards:material-izbira"]["interval"] == 1
    assert kid.get(base + "/progress").json()["session"]["index"] == 1
    second = kid.put(base + "/progress", json=body(2, 1, "know", "cards")).json()
    assert second["answers"]["cards:material-izbira"]["interval"] == 2
    third = kid.put(base + "/progress", json=body(3, 1, "again", "cards")).json()
    assert third["answers"]["cards:material-izbira"]["interval"] == 0
    assert third["answers"]["cards:material-izbira"]["attempts"] == 3
    assert "practice:material-izbira" not in third["answers"]


def test_stale_retry_does_not_duplicate_attempt(lab):
    kid, base, _ = lab
    assert kid.put(base + "/progress", json=body(0, 1, "practice")).status_code == 200
    assert kid.put(base + "/progress", json=body(0, 1, "practice")).status_code == 409
    state = kid.get(base + "/progress").json()
    assert state["answers"]["practice:material-izbira"]["attempts"] == 1


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
