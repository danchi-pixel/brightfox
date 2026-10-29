"""Authenticated source pictures and self-assessed practice; no AI or recordings."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..access import LearnerCtx, learner_in_scope
from ..config import settings
from ..content.registry import content
from ..db import get_db
from ..models import LabProgress
from .learner import TopicId, visible_topic

router = APIRouter(prefix="/api/learners/{lid}/topics/{tid}/lab", tags=["learning-bank"])


def bank(db, ctx, tid):
    t = visible_topic(db, ctx, tid)
    if not t.get("lab"):
        raise HTTPException(404, "Učna zbirka ni na voljo.")
    return t


def state_view(row):
    return {"revision": row.revision, **row.state} if row else {"revision": 0, "answers": {}, "session": None}


@router.get("/progress")
def get_progress(tid: TopicId, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)):
    bank(db, ctx, tid)
    return state_view(db.get(LabProgress, (ctx.learner.id, tid)))


@router.get("/images/{sid}")
def source_image(tid: TopicId, sid: str, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)):
    t = bank(db, ctx, tid)
    source = next((s for s in t["lab"]["sources"] if s["id"] == sid), None)
    if not source:
        raise HTTPException(404, "Slika ni na voljo.")
    scope = content().scope[tid]
    root = (settings.files_dir / "study" / scope / tid).resolve()
    path = (root / source["file"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Slika še ni prenesena. Povej staršem.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


class SessionIn(BaseModel):
    mode: Literal["oral", "mock", "quiz", "images", "cards"]
    queue: list[str] = Field(min_length=1, max_length=200)
    index: int = Field(ge=0, le=200)
    ratings: dict[str, Literal["know", "practice", "again"]] = Field(default_factory=dict, max_length=200)


class SaveIn(BaseModel):
    revision: int = Field(ge=0)
    version: int = Field(ge=1)
    session: SessionIn
    question: str | None = None
    rating: Literal["know", "practice", "again"] | None = None


@router.put("/progress")
def save(tid: TopicId, body: SaveIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)):
    ctx.require_self()
    t = bank(db, ctx, tid)
    if body.version != t["version"]:
        raise HTTPException(409, "Snov se je spremenila. Osveži stran.")
    ids = {q["id"] for q in t["lab"]["questions"]}
    s = body.session
    if (set(s.queue) - ids or len(set(s.queue)) != len(s.queue) or s.index > len(s.queue)
            or set(s.ratings) - set(s.queue) or (body.question is None) != (body.rating is None)
            or body.question is not None and body.question not in s.queue):
        raise HTTPException(400, "Neveljavna vaja.")
    row = db.get(LabProgress, (ctx.learner.id, tid))
    if (row.revision if row else 0) != body.revision:
        raise HTTPException(409, "Napredek je spremenjen v drugem oknu. Osveži stran.")
    state = deepcopy(row.state) if row else {"answers": {}}
    state["session"] = s.model_dump()
    if body.question:
        key = f"{'cards' if s.mode == 'cards' else 'practice'}:{body.question}"
        old = state["answers"].get(key, {})
        interval = min(30, max(1, old.get("interval", 0) * 2)) if body.rating == "know" else 0
        state["answers"][key] = {"rating": body.rating, "attempts": old.get("attempts", 0) + 1,
            "interval": interval, "due": (datetime.now(timezone.utc) + timedelta(days=interval)).isoformat(),
            "updated": datetime.now(timezone.utc).isoformat()}
    if row:
        result = db.execute(update(LabProgress).where(LabProgress.learner_id == ctx.learner.id,
            LabProgress.topic_id == tid, LabProgress.family_id == ctx.family_id,
            LabProgress.revision == body.revision).values(state=state, revision=body.revision + 1))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Osveži napredek in poskusi znova.")
    else:
        db.add(LabProgress(family_id=ctx.family_id, learner_id=ctx.learner.id, topic_id=tid, revision=1, state=state))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Osveži napredek in poskusi znova.")
    return {"revision": body.revision + 1, **state}
