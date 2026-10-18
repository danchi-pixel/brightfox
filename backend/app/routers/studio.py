"""The parent's studio: the family at a glance, topics to check and approve per learner, and how each learner
got on (right first time, the tasks that needed help and what was typed, the study part)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from .. import llm
from ..access import AdminCtx, admin_ctx
from ..content.registry import content, topic_for_family
from ..db import get_db
from ..learning import progress as pg
from ..llm import service as llm_service
from ..models import ContentAccess, Learner, PracticeRun, TopicProgress
from ..timeutil import local_today
from ..tutor import prompts
from ..tutor import service as tutor
from .family import family_learners

router = APIRouter(prefix="/api/studio", tags=["studio"])

TopicId = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,78}$")]


def _learner_brief(lr: Learner) -> dict[str, Any]:
    return {"id": lr.id, "name": lr.name, "avatar": lr.avatar, "color": lr.color}


@router.get("/overview")
def overview(today: str | None = None, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    day = local_today(ctx.family.timezone, today)
    spec, effort = llm_service.route(db, ctx.family_id, "tutor_chat")
    return {
        "family": {"id": ctx.family.id, "name": ctx.family.name},
        "tutor": {"configured": llm.configured(), "model": spec.label, "effort": effort,
                  **tutor.month_usage(db, ctx.family_id, day),
                  "budget_usd": (ctx.family.settings or {}).get("ai_monthly_budget_usd")},
        "subjects": list(prompts.SUBJECTS),
        "learners": [{**_learner_brief(lr), "grade": lr.grade, "tutor_enabled": lr.tutor_enabled,
                      "tutor_daily_limit": lr.tutor_daily_limit,
                      "today_messages": tutor.kid_messages_today(db, lr.id, day),
                      **tutor.month_usage(db, ctx.family_id, day, lr.id)} for lr in family_learners(db, ctx.family_id)],
    }


def _access(db: Session, ctx: AdminCtx, tid: str) -> list[ContentAccess]:
    return list(db.scalars(select(ContentAccess).where(ContentAccess.kind == "topic", ContentAccess.content_id == tid,
                                                       ContentAccess.family_id == ctx.family_id)))


def _access_out(t: dict[str, Any], rows: list[ContentAccess]) -> dict[str, Any]:
    current = [a.learner_id for a in rows if a.version == t["version"]]
    return {"learner_ids": sorted(current),
            # Learners who had an older version: shown as "changed since you approved it".
            "outdated_ids": sorted(a.learner_id for a in rows if a.version != t["version"]),
            "approved": bool(current) and all(a.version == t["version"] for a in rows)}


@router.get("/topics")
def list_topics(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    c = content()
    ids = c.for_family(ctx.family.slug)
    access: dict[str, list[ContentAccess]] = defaultdict(list)
    for a in db.scalars(select(ContentAccess).where(ContentAccess.kind == "topic", ContentAccess.family_id == ctx.family_id)):
        access[a.content_id].append(a)
    runs: dict[str, dict[int, list[PracticeRun]]] = defaultdict(lambda: defaultdict(list))
    for r in db.scalars(select(PracticeRun).where(PracticeRun.family_id == ctx.family_id)):
        runs[r.content_id][r.learner_id].append(r)
    return {"topics": [{**pg.topic_card(c.topics[i]), "scope": "global" if c.scope[i] == "global" else "family",
                        **_access_out(c.topics[i], access[i]),
                        "progress": {str(lid): pg.runs_state(rs) for lid, rs in runs[i].items()}} for i in ids]}


@router.get("/topics/{tid}")
def get_topic(tid: TopicId, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    t = topic_for_family(ctx.family.slug, tid)
    return {"topic": t, **pg.topic_card(t), **_access_out(t, _access(db, ctx, tid))}


class AccessIn(BaseModel):
    version: int = Field(ge=1)
    learner_ids: list[int] = Field(min_length=1, max_length=20)


@router.put("/topics/{tid}/access")
def approve(tid: TopicId, body: AccessIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    """Approve the version the parent just checked, for the learners chosen (the others lose access)."""
    t = topic_for_family(ctx.family.slug, tid)
    if body.version != t["version"]:
        raise HTTPException(409, "This topic has changed since you opened it. Check it again, then approve.")
    mine = {lr.id for lr in family_learners(db, ctx.family_id, include_archived=True)}
    ids = list(dict.fromkeys(body.learner_ids))
    if set(ids) - mine:
        raise HTTPException(404, "Not found")
    db.execute(delete(ContentAccess).where(ContentAccess.kind == "topic", ContentAccess.content_id == tid,
                                           ContentAccess.family_id == ctx.family_id))
    now = datetime.now(timezone.utc)
    for lid in ids:
        db.add(ContentAccess(kind="topic", content_id=tid, learner_id=lid, family_id=ctx.family_id, version=t["version"],
                             approved_by=ctx.user.id, approved_at=now))
    db.commit()
    return _access_out(t, _access(db, ctx, tid))


@router.delete("/topics/{tid}/access")
def unapprove(tid: TopicId, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    t = topic_for_family(ctx.family.slug, tid)
    db.execute(delete(ContentAccess).where(ContentAccess.kind == "topic", ContentAccess.content_id == tid,
                                           ContentAccess.family_id == ctx.family_id))
    db.commit()
    return _access_out(t, [])


@router.get("/topics/{tid}/results")
def topic_results(tid: TopicId, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    """How each learner got on: the latest practice and challenge run at a glance, the study part, and per-task
    totals with the typed mistakes. For parents only."""
    t = topic_for_family(ctx.family.slug, tid)
    practice_ids = [x["id"] for x in t["tasks"]]
    challenge_ids = [x["id"] for x in t.get("challenge", [])]
    by_learner: dict[int, list[PracticeRun]] = defaultdict(list)
    for r in db.scalars(select(PracticeRun).options(selectinload(PracticeRun.results))
                        .where(PracticeRun.family_id == ctx.family_id, PracticeRun.content_id == tid).order_by(PracticeRun.id)):
        by_learner[r.learner_id].append(r)
    progress = {p.learner_id: p for p in db.scalars(select(TopicProgress).where(TopicProgress.family_id == ctx.family_id,
                                                                                TopicProgress.topic_id == tid))}
    learners = {lr.id: lr for lr in family_learners(db, ctx.family_id, include_archived=True)}
    out = []
    for lid in sorted(set(by_learner) | set(progress), key=lambda i: (learners[i].sort_order, i) if i in learners else (0, i)):
        if lid not in learners:
            continue
        runs = by_learner.get(lid, [])
        ch = pg.challenge_state(t, runs)
        out.append({"learner": _learner_brief(learners[lid]), **pg.runs_state(runs),
                    "latest": pg.run_summary(pg.latest(runs, "practice"), practice_ids),
                    "challenge": ch and {**ch, "latest": pg.run_summary(pg.latest(runs, "challenge"), challenge_ids)},
                    "study": pg.study_state(t, progress.get(lid)),
                    "tasks": pg.task_totals(runs, practice_ids + challenge_ids)})
    return {"learners": out}
