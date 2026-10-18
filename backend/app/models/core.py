"""Families, their accounts and their learners.

A **family** is one customer: parents (``admin`` accounts) and kids (``learner`` profiles, each with an
optional ``learner`` account). Every learner-owned table elsewhere carries ``family_id`` and refers to
``learners(family_id, id)`` together, so the database itself refuses a row that mixes two families.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class Family(Base):
    __tablename__ = "families"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Also the name of the family's private content folder (content/data/families/<slug>/).
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(40), default="Europe/Ljubljana")
    language: Mapped[str] = mapped_column(String(5), default="sl")
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | suspended
    # Family-wide preferences: grade scale for tests, monthly AI budget, ...
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Learner(Base):
    """A kid in a family: their own study space (topics, tests, Foxy). Replaces PitchDriven's player profile
    and study profile."""

    __tablename__ = "learners"
    __table_args__ = (UniqueConstraint("family_id", "id", name="uq_learners_family_id_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    avatar: Mapped[str] = mapped_column(String(16), default="🦊")
    color: Mapped[str] = mapped_column(String(20), default="#e8590c")
    # 1–9 primary school (razred), 10–13 secondary school (1.–4. letnik). Unknown until a parent sets it.
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="sl")  # what Foxy and the kid screens use
    interests: Mapped[str | None] = mapped_column(String(200), nullable=True)  # "nogomet", for Foxy's examples
    tutor_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tutor_daily_limit: Mapped[int] = mapped_column(Integer, default=30)
    tutor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # private notes for Foxy from a parent
    # The days the learner usually studies (1 = Monday ... 7 = Sunday) and for how long. Plans use it; a
    # missed day never "breaks" anything.
    rhythm: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    """A sign-in account. ``admin`` = a parent (everything in their own family); ``learner`` = a kid (only
    their own space)."""

    __tablename__ = "users"
    __table_args__ = (
        ForeignKeyConstraint(["family_id", "learner_id"], ["learners.family_id", "learners.id"],
                             ondelete="CASCADE", name="fk_users_learner"),
        CheckConstraint("(role = 'admin' AND learner_id IS NULL) OR (role = 'learner' AND learner_id IS NOT NULL)",
                        name="role_matches_learner"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)  # unique across all families
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(10))  # admin | learner
    learner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    language: Mapped[str | None] = mapped_column(String(5), nullable=True)  # the screens' language for this account
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    """A signed-in browser. Only a SHA-256 of the cookie token is stored."""

    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
