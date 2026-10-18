"""Sign-in and each account's own settings (password, language, sign-out everywhere)."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import auth
from ..access import public, self_ctx
from ..config import settings
from ..db import get_db
from ..models import Family, Learner, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(auth.COOKIE_NAME, token, max_age=max_age, httponly=True, secure=settings.cookie_secure,
                        samesite="strict", path="/")


def _me(db: Session, user: User) -> dict[str, Any]:
    family = db.get(Family, user.family_id)
    learner = db.get(Learner, user.learner_id) if user.learner_id else None
    return {
        "authenticated": True,
        "username": user.username,
        "role": user.role,
        "learner_id": user.learner_id,
        "learner_name": learner.name if learner else None,
        "family": {"id": family.id, "name": family.name} if family else None,
        # The account's own choice, else the learner's, else the family's.
        "language": user.language or (learner.language if learner else None) or (family.language if family else "sl"),
    }


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db), _=Depends(public)) -> dict[str, Any]:
    ident = auth.session_user(auth.cookie_value(request.scope))
    user = db.get(User, ident.id) if ident else None
    if user is None:
        return {"authenticated": False}
    return _me(db, user)


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db),
          _=Depends(public)) -> dict[str, Any]:
    ip = _client_ip(request)
    username = body.username.strip().lower()
    wait = auth.limiter.retry_after(ip, username)
    if wait:
        minutes = max(1, round(wait / 60))
        raise HTTPException(429, f"Too many failed attempts. Try again in about {minutes} minute{'s' if minutes > 1 else ''}.",
                            headers={"Retry-After": str(wait)})
    user = auth.authenticate(db, username, body.password)
    family = db.get(Family, user.family_id) if user else None
    if user is None or family is None or family.status != "active":
        auth.limiter.failure(ip, username)
        raise HTTPException(401, "Wrong username or password.")
    auth.limiter.success(ip, username)
    token, _expires = auth.create_session(db, user, request.headers.get("user-agent"))
    _set_cookie(response, token, settings.session_days * 86400)
    response.headers["Cache-Control"] = "no-store"
    return _me(db, user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db), _=Depends(public)) -> dict[str, Any]:
    auth.end_session(db, auth.cookie_value(request.scope))
    response.delete_cookie(auth.COOKIE_NAME, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict")
    return {"authenticated": False}


class PreferencesBody(BaseModel):
    language: Literal["sl", "en"] | None = None


@router.put("/preferences")
def set_preferences(body: PreferencesBody, db: Session = Depends(get_db),
                    me: auth.Identity = Depends(self_ctx)) -> dict[str, Any]:
    user = db.get(User, me.id)
    if user is None:
        raise HTTPException(401, "Please sign in.")
    if "language" in body.model_fields_set:
        user.language = body.language
    db.commit()
    return _me(db, user)


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


@router.post("/change-password")
def change_password(body: ChangePasswordBody, request: Request, response: Response, db: Session = Depends(get_db),
                    me: auth.Identity = Depends(self_ctx)) -> dict[str, Any]:
    """Change the signed-in account's password; other devices are signed out."""
    user = db.get(User, me.id)
    if user is None or not auth.verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "The current password is not correct.")
    try:
        auth.set_password(db, user, body.new_password)  # also ends every session of this account
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    token, _ = auth.create_session(db, user, request.headers.get("user-agent"))
    _set_cookie(response, token, settings.session_days * 86400)
    return {"changed": True}


@router.post("/logout-everywhere")
def logout_everywhere(response: Response, db: Session = Depends(get_db),
                      me: auth.Identity = Depends(self_ctx)) -> dict[str, Any]:
    auth.end_all_sessions(db, me.id)
    response.delete_cookie(auth.COOKIE_NAME, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict")
    return {"authenticated": False}
