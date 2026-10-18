"""Mock tests ("Poskusni test"): written in the teacher's format, timed, no hints, points at the end.

Parents approve a mock per learner (like topics) and see each learner's result with a grade estimate on the
mock's scale. The learner sees their points and what to repeat, never a grade. Answers are checked in the
browser (as in practice); the server adds up the points from the mock file.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..access import AdminCtx, LearnerCtx, admin_ctx, learner_in_scope
from ..content.checker import Content, grade_for, mock_tasks
from ..content.registry import content
from ..db import get_db
from ..models import ContentAccess, PracticeRun, TaskResult
from ..timeutil import iso, local_today
from .family import family_learners

studio = APIRouter(prefix="/api/studio/mocks", tags=["mocks"])
learner = APIRouter(prefix="/api/learners/{lid}/mocks", tags=["mocks"])

MockId = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,78}$")]


def _mock_for_family(c: Content, slug: str, mid: str) -> dict[str, Any]:
    if mid not in c.mocks or c.scope[mid] not in ("global", slug):
        raise HTTPException(404, "Mock test not found")
    return c.mocks[mid]


def mock_card(m: dict[str, Any]) -> dict[str, Any]:
    tasks = mock_tasks(m)
    return {"id": m["id"], "version": m["version"], "subject": m["subject"], "grade": m["grade"], "title": m["title"],
            "intro": m["intro"], "minutes": m["minutes"], "topics": m["topics"], "tasks": len(tasks),
            "points": sum(t["points"] for t in tasks), "for": m.get("for", [])}


def run_summary(m: dict[str, Any], run: PracticeRun | None, with_grade: bool) -> dict[str, Any] | None:
    if run is None:
        return None
    meta = run.meta or {}
    pts, mx = float(meta.get("points", 0)), float(meta.get("max", 0)) or 1.0
    pct = round(100 * pts / mx)
    by_task = {r.task_id: r for r in run.results}
    tasks = {t["id"]: t for t in mock_tasks(m)}
    out = {"date": iso(run.local_date), "points": pts, "max": mx, "pct": pct, "minutes_used": meta.get("minutes_used"),
           "missed": [{"id": tid, "prompt": tasks[tid]["prompt"][:100], "wrong": list(r.wrong or [])[:3], "points": r.points,
                       "max_points": r.max_points, "topic_id": r.topic_id, "skill_id": r.skill_id}
                      for tid, r in by_task.items() if tid in tasks and (r.points or 0) < (r.max_points or 0)]}
    if with_grade:
        out["grade_estimate"] = grade_for(pct, m.get("scale"))
    return out


def _latest_runs(db: Session, family_id: int, mid: str, learner_id: int | None = None) -> dict[int, PracticeRun]:
    q = (select(PracticeRun).options(selectinload(PracticeRun.results))
         .where(PracticeRun.family_id == family_id, PracticeRun.mode == "mock", PracticeRun.content_id == mid,
                PracticeRun.finished.is_(True)).order_by(PracticeRun.id))
    if learner_id is not None:
        q = q.where(PracticeRun.learner_id == learner_id)
    out: dict[int, PracticeRun] = {}
    for r in db.scalars(q):
        out[r.learner_id] = r
    return out


# --------------------------------------------------------------------------- #
# Parents
# --------------------------------------------------------------------------- #
def _access(db: Session, family_id: int, mid: str) -> list[ContentAccess]:
    return list(db.scalars(select(ContentAccess).where(ContentAccess.kind == "mock", ContentAccess.content_id == mid,
                                                       ContentAccess.family_id == family_id)))


def _access_out(m: dict[str, Any], rows: list[ContentAccess]) -> dict[str, Any]:
    current = [a.learner_id for a in rows if a.version == m["version"]]
    return {"learner_ids": sorted(current), "outdated_ids": sorted(a.learner_id for a in rows if a.version != m["version"]),
            "approved": bool(current) and all(a.version == m["version"] for a in rows)}


@studio.get("")
def list_mocks(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    c = content()
    access: dict[str, list[ContentAccess]] = defaultdict(list)
    for a in db.scalars(select(ContentAccess).where(ContentAccess.kind == "mock", ContentAccess.family_id == ctx.family_id)):
        access[a.content_id].append(a)
    return {"mocks": [{**mock_card(c.mocks[i]), **_access_out(c.mocks[i], access[i])} for i in c.mocks_for_family(ctx.family.slug)]}


@studio.get("/{mid}")
def get_mock(mid: MockId, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    m = _mock_for_family(content(), ctx.family.slug, mid)
    learners = {lr.id: lr for lr in family_learners(db, ctx.family_id, include_archived=True)}
    results = [{"learner": {"id": lid, "name": learners[lid].name, "avatar": learners[lid].avatar, "color": learners[lid].color},
                **(run_summary(m, run, with_grade=True) or {})}
               for lid, run in _latest_runs(db, ctx.family_id, mid).items() if lid in learners]
    return {"mock": m, **mock_card(m), **_access_out(m, _access(db, ctx.family_id, mid)), "results": results}


class AccessIn(BaseModel):
    version: int = Field(ge=1)
    learner_ids: list[int] = Field(min_length=1, max_length=20)


@studio.put("/{mid}/access")
def approve(mid: MockId, body: AccessIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    m = _mock_for_family(content(), ctx.family.slug, mid)
    if body.version != m["version"]:
        raise HTTPException(409, "This mock test has changed since you opened it. Check it again, then approve.")
    mine = {lr.id for lr in family_learners(db, ctx.family_id, include_archived=True)}
    ids = list(dict.fromkeys(body.learner_ids))
    if set(ids) - mine:
        raise HTTPException(404, "Not found")
    db.execute(delete(ContentAccess).where(ContentAccess.kind == "mock", ContentAccess.content_id == mid,
                                           ContentAccess.family_id == ctx.family_id))
    for lid in ids:
        db.add(ContentAccess(kind="mock", content_id=mid, learner_id=lid, family_id=ctx.family_id, version=m["version"],
                             approved_by=ctx.user.id))
    db.commit()
    return _access_out(m, _access(db, ctx.family_id, mid))


@studio.delete("/{mid}/access")
def unapprove(mid: MockId, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    m = _mock_for_family(content(), ctx.family.slug, mid)
    db.execute(delete(ContentAccess).where(ContentAccess.kind == "mock", ContentAccess.content_id == mid,
                                           ContentAccess.family_id == ctx.family_id))
    db.commit()
    return _access_out(m, [])


# --------------------------------------------------------------------------- #
# The learner
# --------------------------------------------------------------------------- #
def visible_mocks(db: Session, c: Content, ctx: LearnerCtx) -> list[str]:
    rows = db.scalars(select(ContentAccess).where(ContentAccess.kind == "mock", ContentAccess.learner_id == ctx.learner.id))
    approved = {a.content_id: a.version for a in rows}
    return [i for i in c.mocks_for_family(ctx.family.slug) if approved.get(i) == c.mocks[i]["version"]]


def _visible_mock(db: Session, ctx: LearnerCtx, mid: str) -> dict[str, Any]:
    c = content()
    if mid not in visible_mocks(db, c, ctx):
        raise HTTPException(404, "Mock test not found")
    return c.mocks[mid]


@learner.get("")
def learner_mocks(db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> list[dict[str, Any]]:
    c = content()
    out = []
    for mid in visible_mocks(db, c, ctx):
        m = c.mocks[mid]
        last = _latest_runs(db, ctx.family_id, mid, ctx.learner.id).get(ctx.learner.id)
        out.append({**mock_card(m), "last": run_summary(m, last, with_grade=ctx.user.is_admin)})
    return out


@learner.get("/{mid}")
def learner_mock(mid: MockId, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    m = _visible_mock(db, ctx, mid)
    return {k: v for k, v in m.items() if k != "scale"}


class MockAnswer(BaseModel):
    right: bool = False
    given: str | None = Field(default=None, max_length=300)
    got_it: bool | None = None  # open tasks: the learner's own check against the solution


class MockRunIn(BaseModel):
    answers: dict[str, MockAnswer] = Field(max_length=60)
    minutes_used: int = Field(ge=0, le=300)
    today: str | None = None


@learner.post("/{mid}/runs", status_code=201)
def record_mock(mid: MockId, body: MockRunIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_self()
    m = _visible_mock(db, ctx, mid)
    tasks = {t["id"]: t for t in mock_tasks(m)}
    if set(body.answers) - set(tasks):
        raise HTTPException(400, "Unknown task.")
    day = local_today(ctx.family.timezone, body.today)
    run = PracticeRun(family_id=ctx.family_id, learner_id=ctx.learner.id, mode="mock", content_id=mid, version=m["version"],
                      finished=True, local_date=day, finished_at=datetime.now(timezone.utc))
    points = 0.0
    for tid, t in tasks.items():
        a = body.answers.get(tid, MockAnswer())
        ok = a.got_it is True if t["kind"] == "open" else a.right
        got = float(t["points"]) if ok else 0.0
        points += got
        run.results.append(TaskResult(family_id=ctx.family_id, learner_id=ctx.learner.id, topic_id=t["topic"], task_id=tid,
                                      skill_id=t.get("skill"), level=t.get("level", 2), kind=t["kind"], first=ok, tries=1,
                                      hints=0, shown=False, got_it=a.got_it, wrong=[a.given[:100]] if a.given and not ok else [],
                                      points=got, max_points=float(t["points"]), local_date=day))
    total = float(sum(t["points"] for t in tasks.values()))
    run.meta = {"points": points, "max": total, "minutes_used": body.minutes_used}
    db.add(run)
    db.commit()
    db.refresh(run)
    return run_summary(m, run, with_grade=ctx.user.is_admin) or {}
