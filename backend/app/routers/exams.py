"""Tests at school, readiness, the daily plan, mastery, knowledge gaps and Moje napake (in a learner's space).

A parent enters a test (date, what's on it, the grade they aim for); the learner sees a countdown, about how
ready they are and today's steps. Parents and the learner see the same numbers; only the parent can enter
or change a test.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..access import LearnerCtx, learner_in_scope
from ..content.registry import content
from ..db import get_db
from ..learning import gaps as gp
from ..learning import plan as pl
from ..learning import service as ls
from ..learning.lab_scope import practice_topic
from ..learning.mastery import WHOLE, SkillMastery, is_good, readiness
from ..learning.progress import challenge_state
from ..models import Exam, ExamScope, PracticeRun, ReviewItem, TaskResult, TopicProgress
from ..timeutil import family_tz, iso, local_today
from ..tutor.prompts import SUBJECTS
from .learner import TaskResultIn, visible_topics
from .mocks import visible_mocks

router = APIRouter(prefix="/api/learners/{lid}", tags=["exams"])


def _visible(db: Session, ctx: LearnerCtx) -> dict[str, dict[str, Any]]:
    c = content()
    return {i: practice_topic(db, ctx, c.topics[i]) for i in visible_topics(db, c, ctx)}


def _scope_skills(exam: Exam, mastery: dict[str, list[SkillMastery]]) -> list[tuple[str, SkillMastery]]:
    out = []
    for sc in exam.scope:
        for s in mastery.get(sc.topic_id, []):
            if not sc.skill_id or s.skill_id == sc.skill_id:
                out.append((sc.topic_id, s))
    return out


def _exam_out(exam: Exam, mastery: dict[str, list[SkillMastery]], topics: dict[str, dict[str, Any]], today: date) -> dict[str, Any]:
    skills = _scope_skills(exam, mastery)
    return {"id": exam.id, "subject": exam.subject, "title": exam.title, "exam_date": iso(exam.exam_date), "kind": exam.kind,
            "target_grade": exam.target_grade, "notes": exam.notes or "", "result_grade": exam.result_grade,
            "days_left": (exam.exam_date - today).days,
            "scope": [{"topic_id": sc.topic_id, "skill_id": sc.skill_id or None,
                       "topic_title": topics[sc.topic_id]["title"] if sc.topic_id in topics else None} for sc in exam.scope],
            "readiness": readiness([s for _, s in skills]),
            "skills": [{"topic_id": tid, "topic_title": topics.get(tid, {}).get("title"), **s.as_dict()} for tid, s in skills]}


def _context(db: Session, ctx: LearnerCtx, today: date):
    topics = _visible(db, ctx)
    results = ls.results_by_topic(db, ctx.learner.id)
    prog = ls.progress_by_topic(db, ctx.learner.id)
    return topics, results, prog, ls.mastery_for(topics, results, prog, today, ls.mock_scores(db, ctx.learner.id))


@router.get("/exams")
def list_exams(today: str | None = None, past: bool = False, db: Session = Depends(get_db),
               ctx: LearnerCtx = Depends(learner_in_scope)) -> list[dict[str, Any]]:
    day = local_today(ctx.family.timezone, today)
    topics, _, _, mastery = _context(db, ctx, day)
    q = select(Exam).where(Exam.learner_id == ctx.learner.id)
    q = q.where(Exam.exam_date < day).order_by(Exam.exam_date.desc()) if past else q.where(Exam.exam_date >= day).order_by(Exam.exam_date)
    return [_exam_out(e, mastery, topics, day) for e in db.scalars(q)]


class ScopeIn(BaseModel):
    topic_id: str = Field(max_length=80)
    skill_id: str | None = Field(default=None, max_length=40)


class ExamIn(BaseModel):
    subject: str
    title: str = Field(min_length=1, max_length=80)
    exam_date: date
    kind: str = Field(default="written", pattern="^(written|oral)$")
    target_grade: int | None = Field(default=None, ge=2, le=5)
    notes: str | None = Field(default=None, max_length=1000)
    result_grade: int | None = Field(default=None, ge=1, le=5)
    scope: list[ScopeIn] = Field(default_factory=list, max_length=20)


def _apply(db: Session, ctx: LearnerCtx, exam: Exam, body: ExamIn) -> None:
    if body.subject not in SUBJECTS:
        raise HTTPException(400, "Unknown subject.")
    topics = _visible(db, ctx)
    for sc in body.scope:
        t = topics.get(sc.topic_id)
        if t is None:
            raise HTTPException(400, "A topic on the test must be approved for this learner first.")
        if sc.skill_id and sc.skill_id not in {s["id"] for s in t.get("skills", [])}:
            raise HTTPException(400, "Unknown skill.")
    exam.subject, exam.title, exam.exam_date, exam.kind = body.subject, body.title.strip(), body.exam_date, body.kind
    exam.target_grade, exam.result_grade, exam.notes = body.target_grade, body.result_grade, (body.notes or "").strip() or None
    exam.scope.clear()
    db.flush()
    seen = set()
    for sc in body.scope:
        key = (sc.topic_id, sc.skill_id or "")
        if key not in seen:
            seen.add(key)
            exam.scope.append(ExamScope(topic_id=sc.topic_id, skill_id=sc.skill_id or ""))


@router.post("/exams", status_code=201)
def create_exam(body: ExamIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_admin()
    exam = Exam(family_id=ctx.family_id, learner_id=ctx.learner.id, created_by=ctx.user.id, subject=body.subject,
                title=body.title, exam_date=body.exam_date)
    db.add(exam)
    _apply(db, ctx, exam, body)
    db.commit()
    day = local_today(ctx.family.timezone)
    topics, _, _, mastery = _context(db, ctx, day)
    return _exam_out(exam, mastery, topics, day)


def _own_exam(db: Session, ctx: LearnerCtx, eid: int) -> Exam:
    exam = db.get(Exam, eid)
    if exam is None or exam.learner_id != ctx.learner.id:
        raise HTTPException(404, "Test not found")
    return exam


@router.put("/exams/{eid}")
def update_exam(eid: int, body: ExamIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_admin()
    exam = _own_exam(db, ctx, eid)
    _apply(db, ctx, exam, body)
    db.commit()
    day = local_today(ctx.family.timezone)
    topics, _, _, mastery = _context(db, ctx, day)
    return _exam_out(exam, mastery, topics, day)


@router.delete("/exams/{eid}")
def delete_exam(eid: int, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_admin()
    db.delete(_own_exam(db, ctx, eid))
    db.commit()
    return {"deleted": eid}


def _done_today(db: Session, ctx: LearnerCtx, day: date) -> set[str]:
    """Which kinds of steps the learner did today, per topic (the plan ticks them off by itself)."""
    done: set[str] = set()
    for tid, mode in db.execute(select(PracticeRun.content_id, PracticeRun.mode).where(
            PracticeRun.learner_id == ctx.learner.id, PracticeRun.local_date == day)):
        done.add("review::" if mode == "review" else f"{mode}:{tid}:")
    tz = family_tz(ctx.family.timezone)
    for tid, updated in db.execute(select(TopicProgress.topic_id, TopicProgress.updated_at)
                                   .where(TopicProgress.learner_id == ctx.learner.id)):
        if updated is not None and (updated if updated.tzinfo else updated.replace(tzinfo=timezone.utc)).astimezone(tz).date() == day:
            done.update({f"learn:{tid}:", f"cards:{tid}:"})
    return done


@router.get("/exams/{eid}")
def exam_detail(eid: int, today: str | None = None, db: Session = Depends(get_db),
                ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    """The test with readiness per skill and the plan up to it."""
    day = local_today(ctx.family.timezone, today)
    exam = _own_exam(db, ctx, eid)
    topics, results, prog, mastery = _context(db, ctx, day)
    runs: dict[str, list[PracticeRun]] = defaultdict(list)
    for r in db.scalars(select(PracticeRun).where(PracticeRun.learner_id == ctx.learner.id)):
        runs[r.content_id].append(r)
    inputs = []
    for tid, s in _scope_skills(exam, mastery):
        t = topics[tid]
        practice = s.parts.get("practice", {"done": 0, "total": 0})
        study = t.get("study") or {}
        known = set((prog[tid].known if tid in prog else []) or [])
        cards_left = sum(1 for c in study.get("cards", []) if (c.get("skill") or WHOLE) in (s.skill_id, WHOLE) and c["back"] not in known)
        ch = challenge_state(t, runs.get(tid, [])) or {}
        inputs.append(pl.SkillInput(tid, t["title"], s.skill_id, s.title, s.mastery,
                                    practice["done"] / practice["total"] if practice["total"] else 1.0,
                                    bool(t.get("study")), cards_left, bool(t.get("challenge")), bool(ch.get("cleared"))))
    in_scope = {sc.topic_id for sc in exam.scope}
    due = ls.due_items(db, ctx.learner.id, day, in_scope if (exam.exam_date - day).days <= 3 else set(), topics)
    # A mock test approved for this learner that covers the test's topics goes on the second-to-last study day.
    c = content()
    mock = next((c.mocks[i] for i in visible_mocks(db, c, ctx) if set(c.mocks[i]["topics"]) & in_scope), None)
    plan = pl.build_plan(day, exam.exam_date, (ctx.learner.rhythm or {}).get("days"), (ctx.learner.rhythm or {}).get("minutes", 20),
                         inputs, len(due), has_mock=mock is not None, done_today=_done_today(db, ctx, day),
                         mock_id=mock["id"] if mock else None, mock_title=mock["title"] if mock else "")
    return {**_exam_out(exam, mastery, topics, day), "plan": plan}


@router.get("/mastery")
def mastery(today: str | None = None, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    day = local_today(ctx.family.timezone, today)
    topics, _, _, m = _context(db, ctx, day)
    return {"topics": [{"topic_id": tid, "title": topics[tid]["title"], "subject": topics[tid]["subject"],
                        "readiness": readiness(skills), "skills": [s.as_dict() for s in skills]} for tid, skills in m.items()]}


@router.get("/gaps")
def gaps(today: str | None = None, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    day = local_today(ctx.family.timezone, today)
    topics, results, prog, m = _context(db, ctx, day)
    nearest: dict[str, int] = {}
    for exam in ls.upcoming_exams(db, ctx.learner.id, day):
        for sc in exam.scope:
            nearest.setdefault(sc.topic_id, (exam.exam_date - day).days)
    wrong = ls.wrong_by_task(db, ctx.learner.id)
    inputs = [gp.TopicInput(t, m[tid], results.get(tid, []), wrong.get(tid, {}), (prog[tid].known if tid in prog else []) or [],
                            (prog[tid].goals if tid in prog else []) or [], nearest.get(tid)) for tid, t in topics.items()]
    overdue = sum(1 for item in db.scalars(select(ReviewItem).where(ReviewItem.learner_id == ctx.learner.id,
        ReviewItem.cleared_at.is_(None), ReviewItem.due_date < day - timedelta(days=3)))
        if _task(topics, item.topic_id, item.item_id))
    return {"gaps": gp.find_gaps(inputs, overdue, day)}


# --------------------------------------------------------------------------- #
# Moje napake
# --------------------------------------------------------------------------- #
def _task(topics: dict[str, dict[str, Any]], tid: str, task_id: str) -> dict[str, Any] | None:
    t = topics.get(tid)
    return next((x for x in (t["tasks"] + t.get("challenge", [])) if x["id"] == task_id), None) if t else None


@router.get("/review")
def review(today: str | None = None, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    """Today's Moje napake (the tasks themselves, with their topic), plus the "popravljeno" count."""
    day = local_today(ctx.family.timezone, today)
    topics = _visible(db, ctx)
    soon = {sc.topic_id for e in ls.upcoming_exams(db, ctx.learner.id, day) if (e.exam_date - day).days <= 3 for sc in e.scope}
    items = ls.due_items(db, ctx.learner.id, day, soon, topics)
    open_count = sum(1 for item in db.scalars(select(ReviewItem).where(ReviewItem.learner_id == ctx.learner.id,
        ReviewItem.cleared_at.is_(None))) if _task(topics, item.topic_id, item.item_id))
    cleared = db.scalar(select(func.count(ReviewItem.id)).where(ReviewItem.learner_id == ctx.learner.id, ReviewItem.cleared_at.is_not(None))) or 0
    return {"items": [{"id": i.id, "topic_id": i.topic_id, "topic_title": topics[i.topic_id]["title"], "box": i.box,
                       "wrong": i.wrong, "task": _task(topics, i.topic_id, i.item_id)} for i in items],
            "open": open_count, "cleared": cleared}


class ReviewIn(BaseModel):
    results: dict[str, TaskResultIn] = Field(max_length=20)  # review item id -> how it went
    today: str | None = None


@router.post("/review/answers")
def review_answers(body: ReviewIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_self()
    day = local_today(ctx.family.timezone, body.today)
    topics = _visible(db, ctx)
    runs: dict[str, PracticeRun] = {}
    moved = cleared = 0
    for item_id, r in body.results.items():
        item = db.get(ReviewItem, int(item_id)) if item_id.isdigit() else None
        if item is None or item.learner_id != ctx.learner.id:
            raise HTTPException(400, "Unknown item.")
        task = _task(topics, item.topic_id, item.item_id)
        if task is None:
            continue
        row = TaskResult(family_id=ctx.family_id, learner_id=ctx.learner.id, topic_id=item.topic_id, task_id=item.item_id,
                         skill_id=task.get("skill"), level=task["level"], kind=task["kind"], first=r.first, tries=r.tries,
                         hints=r.hints, shown=r.shown, got_it=r.got_it, wrong=list(r.wrong), local_date=day)
        run = runs.get(item.topic_id)
        if run is None:
            run = PracticeRun(family_id=ctx.family_id, learner_id=ctx.learner.id, mode="review", content_id=item.topic_id,
                              version=topics[item.topic_id]["version"], finished=True, local_date=day,
                              finished_at=datetime.now(timezone.utc))
            runs[item.topic_id] = run
            db.add(run)
        run.results.append(row)
        good = is_good(ls.Result(item.item_id, task["kind"], r.first, r.shown, r.got_it, day))
        ls.answer_item(item, good, day)
        if r.wrong:
            item.wrong = r.wrong[-1]
        moved += 1
        cleared += item.cleared_at is not None
    db.commit()
    return {"answered": moved, "cleared": cleared}


@router.get("/week")
def week(today: str | None = None, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    """This week's rhythm (Monday to Sunday): which days had any learning. It resets every Monday; nothing to break."""
    day = local_today(ctx.family.timezone, today)
    monday = day - timedelta(days=day.weekday())
    active = {d for (d,) in db.execute(select(PracticeRun.local_date).where(PracticeRun.learner_id == ctx.learner.id,
                                                                             PracticeRun.local_date >= monday))}
    usual = set((ctx.learner.rhythm or {}).get("days") or [])
    return {"days": [{"date": iso(monday + timedelta(days=i)), "active": (monday + timedelta(days=i)) in active,
                      "usual": (i + 1) in usual, "today": monday + timedelta(days=i) == day} for i in range(7)],
            "trophies": _trophies(db, ctx)}


def _trophies(db: Session, ctx: LearnerCtx) -> dict[str, int]:
    """Collected, never lost: Champions League levels won and mistakes corrected for good."""
    cups = db.scalar(select(func.count(func.distinct(PracticeRun.content_id))).where(
        PracticeRun.learner_id == ctx.learner.id, PracticeRun.mode == "challenge", PracticeRun.finished.is_(True))) or 0
    fixed = db.scalar(select(func.count(ReviewItem.id)).where(ReviewItem.learner_id == ctx.learner.id,
                                                              ReviewItem.cleared_at.is_not(None))) or 0
    return {"cups": cups, "corrected": fixed}
