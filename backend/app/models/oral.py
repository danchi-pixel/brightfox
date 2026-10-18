"""The oral exam ("ustno spraševanje"): Foxy asks a topic's oral questions aloud, the learner types the answer,
and Foxy checks it against the key points (right / partly / not yet, with one or two sentences of feedback)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow


class OralSession(Base):
    __tablename__ = "oral_sessions"
    __table_args__ = (ForeignKeyConstraint(["family_id", "learner_id"], ["learners.family_id", "learners.id"],
                                           ondelete="CASCADE", name="fk_oral_sessions_learner"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, index=True)
    learner_id: Mapped[int] = mapped_column(Integer, index=True)
    topic_id: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    local_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    turns: Mapped[list[OralTurn]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="OralTurn.id")


class OralTurn(Base):
    __tablename__ = "oral_turns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("oral_sessions.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[str] = mapped_column(String(40))
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(10))  # right | partly | not_yet
    feedback: Mapped[str] = mapped_column(Text, default="")
    llm_call_id: Mapped[int | None] = mapped_column(ForeignKey("llm_calls.id", ondelete="SET NULL"), nullable=True)
    local_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    session: Mapped[OralSession] = relationship(back_populates="turns")
