"""The parent's family settings: the family itself, its learners and its sign-in accounts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import auth
from ..access import AdminCtx, admin_ctx
from ..db import get_db
from ..models import Family, Learner, User
from ..timeutil import family_tz, iso, local_today

router = APIRouter(prefix="/api/family", tags=["family"])


def family_out(f: Family) -> dict[str, Any]:
    return {"id": f.id, "slug": f.slug, "name": f.name, "timezone": f.timezone, "language": f.language,
            "settings": f.settings or {}}


def learner_out(learner: Learner, account: User | None = None) -> dict[str, Any]:
    return {"id": learner.id, "name": learner.name, "avatar": learner.avatar, "color": learner.color,
            "grade": learner.grade, "language": learner.language, "interests": learner.interests or "",
            "tutor_enabled": learner.tutor_enabled, "tutor_daily_limit": learner.tutor_daily_limit,
            "tutor_notes": learner.tutor_notes or "", "rhythm": learner.rhythm, "archived": learner.archived,
            "sort_order": learner.sort_order, "username": account.username if account else None}


def family_learners(db: Session, family_id: int, include_archived: bool = False) -> list[Learner]:
    q = select(Learner).where(Learner.family_id == family_id)
    if not include_archived:
        q = q.where(Learner.archived.is_(False))
    return list(db.scalars(q.order_by(Learner.sort_order, Learner.id)))


def _accounts_by_learner(db: Session, family_id: int) -> dict[int, User]:
    return {u.learner_id: u for u in db.scalars(select(User).where(User.family_id == family_id, User.learner_id.is_not(None)))}


@router.get("")
def get_family(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    accounts = _accounts_by_learner(db, ctx.family_id)
    return {**family_out(ctx.family),
            "learners": [learner_out(lr, accounts.get(lr.id)) for lr in family_learners(db, ctx.family_id, True)]}


class FamilyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    timezone: str | None = Field(default=None, max_length=40)
    language: Literal["sl", "en"] | None = None


@router.patch("")
def patch_family(body: FamilyPatch, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    f = db.get(Family, ctx.family_id)
    data = body.model_dump(exclude_unset=True)
    if "timezone" in data and data["timezone"] is not None and family_tz(data["timezone"]).key != data["timezone"]:
        raise HTTPException(400, "Unknown time zone.")
    for k, v in data.items():
        if v is not None:
            setattr(f, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return family_out(f)


# --------------------------------------------------------------------------- #
# Learners
# --------------------------------------------------------------------------- #
class Rhythm(BaseModel):
    days: list[int] = Field(default_factory=lambda: [1, 2, 3, 4], max_length=7)  # 1 = Monday ... 7 = Sunday
    minutes: int = Field(default=20, ge=5, le=120)


class LearnerIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    avatar: str = Field(default="🦊", max_length=16)
    color: str = Field(default="#e8590c", pattern=r"^#[0-9a-fA-F]{6}$")
    grade: int | None = Field(default=None, ge=1, le=13)
    language: Literal["sl", "en"] = "sl"
    interests: str | None = Field(default=None, max_length=200)
    tutor_enabled: bool = True
    tutor_daily_limit: int = Field(default=30, ge=0, le=200)
    tutor_notes: str | None = Field(default=None, max_length=1000)
    rhythm: Rhythm | None = None
    archived: bool = False
    sort_order: int = 0


class LearnerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    avatar: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    grade: int | None = Field(default=None, ge=1, le=13)
    language: Literal["sl", "en"] | None = None
    interests: str | None = Field(default=None, max_length=200)
    tutor_enabled: bool | None = None
    tutor_daily_limit: int | None = Field(default=None, ge=0, le=200)
    tutor_notes: str | None = Field(default=None, max_length=1000)
    rhythm: Rhythm | None = None
    archived: bool | None = None
    sort_order: int | None = None


def _clean_rhythm(r: Rhythm | None) -> dict[str, Any] | None:
    if r is None:
        return None
    days = sorted({d for d in r.days if 1 <= d <= 7})
    return {"days": days, "minutes": r.minutes}


def _own_learner(db: Session, ctx: AdminCtx, lid: int) -> Learner:
    learner = db.get(Learner, lid)
    if learner is None or learner.family_id != ctx.family_id:
        raise HTTPException(404, "Not found")
    return learner


@router.post("/learners", status_code=201)
def create_learner(body: LearnerIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    data = body.model_dump()
    data["rhythm"] = _clean_rhythm(body.rhythm)
    data["name"] = data["name"].strip()
    for k in ("interests", "tutor_notes"):
        data[k] = (data[k] or "").strip() or None
    learner = Learner(family_id=ctx.family_id, **data)
    db.add(learner)
    db.commit()
    return learner_out(learner)


@router.patch("/learners/{lid}")
def patch_learner(lid: int, body: LearnerPatch, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    learner = _own_learner(db, ctx, lid)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "rhythm":
            learner.rhythm = _clean_rhythm(body.rhythm)
        elif k in ("interests", "tutor_notes"):
            setattr(learner, k, (v or "").strip() or None)
        elif k == "grade":
            learner.grade = v  # None clears it
        elif v is not None:
            setattr(learner, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return learner_out(learner, _accounts_by_learner(db, ctx.family_id).get(learner.id))


# --------------------------------------------------------------------------- #
# Foxy and AI: which model does each job, the monthly budget, what it costs
# --------------------------------------------------------------------------- #
def _ai_out(db: Session, ctx: AdminCtx, today: str | None) -> dict[str, Any]:
    from ..llm import service as llm_service
    from ..llm.models import JOBS, MODELS, approved_models
    from ..models import LlmCall

    day = local_today(ctx.family.timezone, today)
    jobs = []
    for job, meta in JOBS.items():
        spec, effort = llm_service.route(db, ctx.family_id, job)
        n, cost = db.execute(select(func.count(LlmCall.id), func.coalesce(func.sum(LlmCall.cost_usd), 0.0))
                             .where(LlmCall.family_id == ctx.family_id, LlmCall.job == job,
                                    LlmCall.local_date >= day.replace(day=1), LlmCall.outcome != "imported")).one()
        # The family's own average over its last 200 answers, as "about $X per 100 answers".
        recent = [c for (c,) in db.execute(select(LlmCall.cost_usd).where(
            LlmCall.family_id == ctx.family_id, LlmCall.job == job, LlmCall.model == spec.id,
            LlmCall.outcome != "imported").order_by(LlmCall.id.desc()).limit(200))]
        jobs.append({"job": job, "label": meta["label"], "model": spec.id, "effort": effort,
                     "options": [{"id": m, "label": MODELS[m].label, "tier": MODELS[m].tier} for m in approved_models(job)],
                     "month_calls": n, "month_cost_usd": round(float(cost), 4),
                     "per_100_usd": round(sum(recent) / len(recent) * 100, 2) if recent else None})
    return {"jobs": jobs, "budget_usd": (ctx.family.settings or {}).get("ai_monthly_budget_usd")}


@router.get("/ai")
def get_ai(today: str | None = None, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    return _ai_out(db, ctx, today)


class AiRouteIn(BaseModel):
    job: Literal["tutor_chat", "oral_grading", "open_feedback"]
    model: str = Field(max_length=60)
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None


class AiIn(BaseModel):
    routes: list[AiRouteIn] = Field(default_factory=list, max_length=3)
    budget_usd: float | None = Field(default=None, ge=0, le=1000)


@router.put("/ai")
def set_ai(body: AiIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    from ..llm.models import approved_models
    from ..models import LlmRoute

    for r in body.routes:
        if r.model not in approved_models(r.job):
            raise HTTPException(400, "That model isn't available for this job yet (it hasn't passed the checks).")
        row = db.get(LlmRoute, (ctx.family_id, r.job))
        if row is None:
            row = LlmRoute(family_id=ctx.family_id, job=r.job, model=r.model)
            db.add(row)
        row.model, row.effort, row.updated_by = r.model, r.effort, ctx.user.id
        row.updated_at = datetime.now(timezone.utc)
    f = db.get(Family, ctx.family_id)
    if "budget_usd" in body.model_fields_set:
        f.settings = {**(f.settings or {}), "ai_monthly_budget_usd": body.budget_usd}
    db.commit()
    return _ai_out(db, AdminCtx(ctx.user, f), None)


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
def _account_out(u: User, names: dict[int, str]) -> dict[str, Any]:
    return {"id": u.id, "username": u.username, "role": u.role, "learner_id": u.learner_id,
            "learner_name": names.get(u.learner_id) if u.learner_id else None, "created_at": iso(u.created_at)}


def _names(db: Session, family_id: int) -> dict[int, str]:
    return dict(db.execute(select(Learner.id, Learner.name).where(Learner.family_id == family_id)).all())


@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> list[dict[str, Any]]:
    names = _names(db, ctx.family_id)
    users = db.scalars(select(User).where(User.family_id == ctx.family_id).order_by(User.role, User.username))
    return [_account_out(u, names) for u in users]


class AccountIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
    role: Literal["admin", "learner"] = "learner"
    learner_id: int | None = None


@router.post("/accounts", status_code=201)
def create_account(body: AccountIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    try:
        user = auth.create_account(db, ctx.family_id, body.username, body.password, role=body.role,
                                   learner_id=body.learner_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _account_out(user, _names(db, ctx.family_id))


class AccountPatch(BaseModel):
    password: str | None = Field(default=None, min_length=1, max_length=256)


def _own_account(db: Session, ctx: AdminCtx, uid: int) -> User:
    user = db.get(User, uid)
    if user is None or user.family_id != ctx.family_id:
        raise HTTPException(404, "Not found")
    return user


@router.patch("/accounts/{uid}")
def update_account(uid: int, body: AccountPatch, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    """A parent sets a new password for an account in the family (that account is signed out everywhere)."""
    user = _own_account(db, ctx, uid)
    if body.password:
        try:
            auth.set_password(db, user, body.password)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    return _account_out(user, _names(db, ctx.family_id))


@router.delete("/accounts/{uid}")
def delete_account(uid: int, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx)) -> dict[str, Any]:
    user = _own_account(db, ctx, uid)
    if user.id == ctx.user.id:
        raise HTTPException(400, "You can't delete the account you're signed in with.")
    db.delete(user)
    db.commit()
    auth._cache.clear()
    return {"deleted": uid}
