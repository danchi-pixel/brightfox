"""A learner's own space: their home, the topics a parent approved for them, practice runs and the study part.

The learner may record their own work; a parent of the same family may look (a preview that is never
saved). Anyone else gets 404 (``learner_in_scope``).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import llm
from ..access import LearnerCtx, learner_in_scope
from ..content.checker import Content, goal_list
from ..content.registry import content
from ..content.visibility import visible_ids
from ..db import get_db
from ..learning import progress as pg
from ..learning.service import note_run
from ..models import ContentAccess, PracticeRun, TaskResult, TopicProgress, TutorChat, User
from ..timeutil import local_today
from ..tutor import service as tutor

router = APIRouter(prefix="/api/learners/{lid}", tags=["learner"])

TopicId = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,78}$")]


def visible_topics(db: Session, c: Content, ctx: LearnerCtx) -> list[str]:
    """Topics this learner may open: approved in their current version, newest first."""
    return visible_ids(db, c, ctx, "topic")


def visible_topic(db: Session, ctx: LearnerCtx, tid: str) -> dict[str, Any]:
    c = content()
    if tid not in visible_topics(db, c, ctx):
        raise HTTPException(404, "Topic not found")
    return c.topics[tid]


def viewer_lang(db: Session, ctx: LearnerCtx) -> str:
    """The language of the screens for whoever is looking (a parent may prefer another one)."""
    user = db.get(User, ctx.user.id)
    if ctx.is_self:
        return (user.language if user else None) or ctx.learner.language or "sl"
    return (user.language if user else None) or ctx.family.language or "sl"


@router.get("/home")
def home(today: str | None = None, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    c = content()
    lr = ctx.learner
    day = local_today(ctx.family.timezone, today)
    runs: dict[str, list[PracticeRun]] = defaultdict(list)
    for r in db.scalars(select(PracticeRun).where(PracticeRun.learner_id == lr.id).order_by(PracticeRun.id)):
        runs[r.content_id].append(r)
    prog = {p.topic_id: p for p in db.scalars(select(TopicProgress).where(TopicProgress.learner_id == lr.id))}
    q = select(TutorChat).where(TutorChat.learner_id == lr.id)
    if ctx.is_self:
        q = q.where(TutorChat.parent_test.is_(False))
    chats = list(db.scalars(q.order_by(TutorChat.updated_at.desc(), TutorChat.id.desc()).limit(30)))
    used = tutor.kid_messages_today(db, lr.id, day)
    return {
        "learner": {"id": lr.id, "name": lr.name, "avatar": lr.avatar, "color": lr.color, "grade": lr.grade},
        "owner": ctx.is_self,
        "lang": lr.language or "sl",  # a parent's preview shows the learner's language
        "tutor": {"configured": llm.configured(), "enabled": lr.tutor_enabled, "daily_limit": lr.tutor_daily_limit,
                  "left_today": max(0, lr.tutor_daily_limit - used)},
        "topics": [{**pg.topic_card(c.topics[i]), **pg.runs_state(runs.get(i, [])),
                    "challenge_state": pg.challenge_state(c.topics[i], runs.get(i, [])),
                    "study_state": pg.study_state(c.topics[i], prog.get(i))} for i in visible_topics(db, c, ctx)],
        "chats": tutor.chat_cards(db, chats, with_cost=ctx.user.is_admin),
    }


@router.get("/topics/{tid}")
def get_topic(tid: TopicId, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    t = visible_topic(db, ctx, tid)
    # The parent helper card is for parents; kids get the rest of the file.
    return {k: v for k, v in t.items() if k != "parent" or ctx.user.is_admin}


class TaskResultIn(BaseModel):
    first: bool = False  # right on the first try
    tries: int = Field(default=0, ge=0, le=50)
    hints: int = Field(default=0, ge=0, le=3)
    shown: bool = False  # looked at the solution
    got_it: bool | None = None  # open tasks: the child's own check, "I've got it" / "not yet"
    # What was typed (or picked) before the right answer, so parents (and the next topic) see the mistakes.
    wrong: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=5)


class RunIn(BaseModel):
    results: dict[str, TaskResultIn] = Field(max_length=40)
    finished: bool = False
    challenge: bool = False  # a run of the "Liga prvakov" level
    today: str | None = None


@router.post("/topics/{tid}/runs", status_code=201)
def record_run(tid: TopicId, body: RunIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_self()
    t = visible_topic(db, ctx, tid)
    tasks = t.get("challenge", []) if body.challenge else t["tasks"]
    if body.challenge:
        if not tasks:
            raise HTTPException(404, "This topic has no challenge level.")
        earlier = db.scalars(select(PracticeRun).where(PracticeRun.learner_id == ctx.learner.id, PracticeRun.content_id == tid))
        if not (pg.challenge_state(t, list(earlier)) or {}).get("unlocked"):
            raise HTTPException(409, "The challenge opens after the practice is finished once.")
    by_id = {x["id"]: x for x in tasks}
    if set(body.results) - set(by_id):
        raise HTTPException(400, "Unknown task.")
    day = local_today(ctx.family.timezone, body.today)
    run = PracticeRun(family_id=ctx.family_id, learner_id=ctx.learner.id, mode="challenge" if body.challenge else "practice",
                      content_id=tid, version=t["version"], finished=body.finished, local_date=day,
                      finished_at=datetime.now(timezone.utc) if body.finished else None)
    for task_id, r in body.results.items():
        task = by_id[task_id]
        run.results.append(TaskResult(family_id=ctx.family_id, learner_id=ctx.learner.id, topic_id=tid, task_id=task_id,
                                      skill_id=task.get("skill"), level=task["level"], kind=task["kind"], first=r.first,
                                      tries=r.tries, hints=r.hints, shown=r.shown, got_it=r.got_it, wrong=list(r.wrong),
                                      local_date=day))
    db.add(run)
    note_run(db, run, day)  # tasks that needed help go into Moje napake
    db.commit()
    return {"id": run.id}


class ProgressIn(BaseModel):
    known: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=80)
    goals: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=8)


@router.put("/topics/{tid}/progress")
def save_progress(tid: TopicId, body: ProgressIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    """The learner's own study part: the flashcards they know and the goals they ticked (by goal id)."""
    ctx.require_self()
    t = visible_topic(db, ctx, tid)
    st = t.get("study")
    if not st:
        raise HTTPException(404, "This topic has no study part.")
    backs = {card["back"] for card in st.get("cards", [])}
    goal_ids = {g["id"] for g in goal_list(st)}
    if set(body.known) - backs or set(body.goals) - goal_ids:
        raise HTTPException(400, "Unknown card or goal.")
    p = db.get(TopicProgress, (ctx.learner.id, tid))
    if p is None:
        p = TopicProgress(learner_id=ctx.learner.id, topic_id=tid, family_id=ctx.family_id)
        db.add(p)
    p.known = list(dict.fromkeys(body.known))
    p.goals = [g for g in (g["id"] for g in goal_list(st)) if g in set(body.goals)]
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    return pg.study_state(t, p) or {}


def runs_with_results(db: Session, learner_id: int, tid: str) -> list[PracticeRun]:
    return list(db.scalars(select(PracticeRun).options(selectinload(PracticeRun.results))
                           .where(PracticeRun.learner_id == learner_id, PracticeRun.content_id == tid).order_by(PracticeRun.id)))
