"""Reads a learner's practice and progress from the database and feeds the pure formulas (mastery, plan,
gaps, review)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Exam, PracticeRun, ReviewItem, TaskResult, TopicProgress
from . import review as rv
from .mastery import Result, SkillMastery, topic_mastery
from .progress import tricky


def results_by_topic(db: Session, learner_id: int) -> dict[str, list[Result]]:
    out: dict[str, list[Result]] = defaultdict(list)
    rows = db.execute(select(TaskResult.topic_id, TaskResult.task_id, TaskResult.kind, TaskResult.first, TaskResult.shown,
                             TaskResult.got_it, TaskResult.local_date, TaskResult.run_id)
                      .where(TaskResult.learner_id == learner_id).order_by(TaskResult.id))
    for topic_id, *rest in rows:
        out[topic_id].append(Result(*rest))
    return out


def wrong_by_task(db: Session, learner_id: int) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for topic_id, task_id, wrong in db.execute(select(TaskResult.topic_id, TaskResult.task_id, TaskResult.wrong)
                                               .where(TaskResult.learner_id == learner_id).order_by(TaskResult.id.desc())):
        for w in wrong or []:
            if w not in out[topic_id][task_id]:
                out[topic_id][task_id].append(w)
    return out


def progress_by_topic(db: Session, learner_id: int) -> dict[str, TopicProgress]:
    return {p.topic_id: p for p in db.scalars(select(TopicProgress).where(TopicProgress.learner_id == learner_id))}


def mock_scores(db: Session, learner_id: int) -> dict[str, dict[str, tuple[float, float]]]:
    """Points per topic and skill from the latest finished run of each mock test: topic -> skill -> (points, max)."""
    latest: dict[str, int] = {}
    for run_id, mid in db.execute(select(PracticeRun.id, PracticeRun.content_id).where(
            PracticeRun.learner_id == learner_id, PracticeRun.mode == "mock", PracticeRun.finished.is_(True)).order_by(PracticeRun.id)):
        latest[mid] = run_id
    out: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    if latest:
        for topic_id, skill_id, pts, mx in db.execute(select(TaskResult.topic_id, TaskResult.skill_id, TaskResult.points, TaskResult.max_points)
                                                      .where(TaskResult.run_id.in_(list(latest.values())))):
            acc = out[topic_id][skill_id or "_topic"]
            acc[0] += pts or 0.0
            acc[1] += mx or 0.0
    return {tid: {sk: (v[0], v[1]) for sk, v in skills.items()} for tid, skills in out.items()}


def mastery_for(topics: dict[str, dict[str, Any]], results: dict[str, list[Result]], prog: dict[str, TopicProgress],
                today: date, mocks: dict[str, dict[str, tuple[float, float]]] | None = None) -> dict[str, list[SkillMastery]]:
    return {tid: topic_mastery(t, results.get(tid, []), (prog[tid].known if tid in prog else []) or [],
                               (prog[tid].goals if tid in prog else []) or [], today, (mocks or {}).get(tid))
            for tid, t in topics.items()}


def upcoming_exams(db: Session, learner_id: int, today: date) -> list[Exam]:
    return list(db.scalars(select(Exam).where(Exam.learner_id == learner_id, Exam.exam_date >= today).order_by(Exam.exam_date)))


# --------------------------------------------------------------------------- #
# Moje napake
# --------------------------------------------------------------------------- #
def note_run(db: Session, run: PracticeRun, today: date) -> None:
    """After a practice or challenge run: a task that needed help goes into Moje napake (back to box 1 if it
    was there already). Nothing is committed here."""
    for r in run.results:
        if not tricky(r):
            continue
        item = db.scalars(select(ReviewItem).where(ReviewItem.learner_id == run.learner_id, ReviewItem.topic_id == r.topic_id,
                                                   ReviewItem.item_kind == "task", ReviewItem.item_id == r.task_id)).first()
        if item is None:
            item = ReviewItem(family_id=run.family_id, learner_id=run.learner_id, topic_id=r.topic_id, item_kind="task",
                              item_id=r.task_id, skill_id=r.skill_id)
            db.add(item)
        item.box, item.due_date, item.cleared_at = 1, today + timedelta(days=rv.INTERVALS[1]), None
        item.wrong = (r.wrong or [None])[-1]


def due_items(db: Session, learner_id: int, today: date, topics_in_exam_soon: set[str],
              topics: dict[str, dict[str, Any]] | None = None) -> list[ReviewItem]:
    """Due today (oldest first), plus everything of a topic on a test within 3 days; at most 10."""
    items = list(db.scalars(select(ReviewItem).where(ReviewItem.learner_id == learner_id, ReviewItem.cleared_at.is_(None))
                            .order_by(ReviewItem.due_date, ReviewItem.id)))
    allowed = {(tid, task["id"]) for tid, topic in (topics or {}).items()
               for task in topic["tasks"] + topic.get("challenge", [])}
    due = [i for i in items if (topics is None or (i.topic_id, i.item_id) in allowed)
           and (i.due_date <= today or i.topic_id in topics_in_exam_soon)]
    return due[:rv.PER_DAY]


def answer_item(item: ReviewItem, good: bool, today: date) -> None:
    box, due, cleared = rv.after_answer(item.box, good, today)
    item.box, item.due_date = box, due
    item.cleared_at = datetime.now(timezone.utc) if cleared else None
