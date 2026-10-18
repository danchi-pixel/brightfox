"""Who is asking, and what they may see or change.

Every ``/api`` route depends on exactly one of these (``tests/test_tenancy.py`` checks it):

* ``public``: no sign-in (health, login, status, logout).
* ``self_ctx``: any signed-in account, about itself only (password, language, sign-out).
* ``admin_ctx``: a parent, inside their own family.
* ``learner_in_scope``: one learner's space (``/api/learners/{lid}/...``), for that learner themselves or a
  parent of the same family. Anyone else gets 404, so it never shows whether a learner exists.

``LearnerCtx.is_self`` is True only for the learner's own account: writes that record a kid's work require
it, so a parent's preview never ends up in the kid's progress.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .auth import Identity
from .db import get_db
from .models import Family, Learner


def public() -> None:
    """Marks a route that needs no sign-in."""
    return None


def _identity(request: Request) -> Identity:
    user = request.scope.get("state", {}).get("user")
    if not isinstance(user, Identity):
        raise HTTPException(401, "Please sign in.")
    return user


def self_ctx(request: Request) -> Identity:
    return _identity(request)


@dataclass(frozen=True)
class AdminCtx:
    user: Identity
    family: Family

    @property
    def family_id(self) -> int:
        return self.family.id


def admin_ctx(request: Request, db: Session = Depends(get_db)) -> AdminCtx:
    user = _identity(request)
    if not user.is_admin:
        raise HTTPException(404, "Not found")
    family = db.get(Family, user.family_id)
    if family is None or family.status != "active":
        raise HTTPException(401, "Please sign in.")
    return AdminCtx(user, family)


@dataclass(frozen=True)
class LearnerCtx:
    user: Identity
    family: Family
    learner: Learner

    @property
    def family_id(self) -> int:
        return self.family.id

    @property
    def is_self(self) -> bool:
        return self.user.learner_id == self.learner.id

    def require_self(self) -> None:
        if not self.is_self:
            raise HTTPException(403, "Only the learner can record their own work. Parents can preview instead.")

    def require_admin(self) -> None:
        if not self.user.is_admin:
            raise HTTPException(403, "Only a parent can do that.")


def learner_in_scope(lid: int, request: Request, db: Session = Depends(get_db)) -> LearnerCtx:
    user = _identity(request)
    learner = db.get(Learner, lid)
    if learner is None or learner.family_id != user.family_id or (learner.archived and not user.is_admin):
        raise HTTPException(404, "Not found")
    if not user.is_admin and user.learner_id != lid:
        raise HTTPException(404, "Not found")
    family = db.get(Family, user.family_id)
    if family is None or family.status != "active":
        raise HTTPException(401, "Please sign in.")
    return LearnerCtx(user, family, learner)


# The route audit looks for exactly one of these in every /api route's dependencies.
ACCESS_DEPENDENCIES = (public, self_ctx, admin_ctx, learner_in_scope)
