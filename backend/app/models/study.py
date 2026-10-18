"""What each learner does: topic access, practice runs (one row per task), study progress, Foxy chats with
their photos, and the AI cost ledger.

Content (topics, mocks) lives in JSON files, not here; rows refer to it by string id + version. Every row
that belongs to a learner refers to ``learners(family_id, id)`` with both columns, so a row can never mix
two families.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, ForeignKeyConstraint, Index, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow


def _learner_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["family_id", "learner_id"], ["learners.family_id", "learners.id"],
                                ondelete="CASCADE", name=f"fk_{table}_learner")


class ContentAccess(Base):
    """A parent approved this version of a topic (or mock) for this learner. Visible only while ``version``
    equals the file's current version: a changed file waits for a new check."""

    __tablename__ = "content_access"
    __table_args__ = (_learner_fk("content_access"),)
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)  # topic | mock
    content_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    learner_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, index=True)
    version: Mapped[int] = mapped_column(Integer)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PracticeRun(Base):
    """One go at a topic's practice (or its challenge, a review session or a mock test)."""

    __tablename__ = "practice_runs"
    __table_args__ = (_learner_fk("practice_runs"), Index("ix_practice_runs_learner_content", "learner_id", "content_id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, index=True)
    learner_id: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(10), default="practice")  # practice | challenge | review | mock
    content_id: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    local_date: Mapped[date] = mapped_column(Date)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # mock: minutes used, points ...
    results: Mapped[list[TaskResult]] = relationship(back_populates="run", cascade="all, delete-orphan",
                                                     order_by="TaskResult.id")


class TaskResult(Base):
    """How one task went in one run. Never a score shown to the child: mastery, gaps and Moje napake are
    computed from these rows."""

    __tablename__ = "task_results"
    __table_args__ = (_learner_fk("task_results"),
                      Index("ix_task_results_learner_topic_task", "learner_id", "topic_id", "task_id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("practice_runs.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[int] = mapped_column(Integer)
    learner_id: Mapped[int] = mapped_column(Integer)
    topic_id: Mapped[str] = mapped_column(String(80))  # the topic the task comes from (a mock mixes topics)
    task_id: Mapped[str] = mapped_column(String(40))
    skill_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    level: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))  # choice | number | text | open
    first: Mapped[bool] = mapped_column(Boolean, default=False)  # right on the first try
    tries: Mapped[int] = mapped_column(Integer, default=0)
    hints: Mapped[int] = mapped_column(Integer, default=0)
    shown: Mapped[bool] = mapped_column(Boolean, default=False)  # looked at the solution
    got_it: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # open tasks: the child's own check
    wrong: Mapped[list[str]] = mapped_column(JSON, default=list)  # what was typed before the right answer
    points: Mapped[float | None] = mapped_column(Float, nullable=True)  # mocks only
    max_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    local_date: Mapped[date] = mapped_column(Date)
    run: Mapped[PracticeRun] = relationship(back_populates="results")


class TopicProgress(Base):
    """The learner's own study part of a topic: flashcards they know (by the card's back) and the "I can"
    goals they ticked (by goal id)."""

    __tablename__ = "topic_progress"
    __table_args__ = (_learner_fk("topic_progress"),)
    learner_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, index=True)
    known: Mapped[list[str]] = mapped_column(JSON, default=list)
    goals: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TutorChat(Base):
    """A chat with Foxy. Parents read every chat (the kids are told); a parent's own tries are marked
    ``parent_test`` and hidden from the kid."""

    __tablename__ = "tutor_chats"
    __table_args__ = (_learner_fk("tutor_chats"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, index=True)
    learner_id: Mapped[int] = mapped_column(Integer, index=True)
    subject: Mapped[str] = mapped_column(String(20))
    topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # "Vprašaj Foxyja" from a topic
    task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(80), default="")
    parent_test: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    messages: Mapped[list[TutorMessage]] = relationship(back_populates="chat", cascade="all, delete-orphan",
                                                        order_by="TutorMessage.id")


class TutorMessage(Base):
    __tablename__ = "tutor_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("tutor_chats.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    text: Mapped[str] = mapped_column(Text, default="")
    llm_call_id: Mapped[int | None] = mapped_column(ForeignKey("llm_calls.id", ondelete="SET NULL"), nullable=True)
    local_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    chat: Mapped[TutorChat] = relationship(back_populates="messages")
    attachments: Mapped[list[Attachment]] = relationship(back_populates="message", cascade="all, delete-orphan",
                                                         order_by="Attachment.id")


class Attachment(Base):
    """A photo sent with a message. The file lives in data/files/<family_id>/<learner_id>/ and is never
    served publicly."""

    __tablename__ = "attachments"
    __table_args__ = (_learner_fk("attachments"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("tutor_messages.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[int] = mapped_column(Integer)
    learner_id: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(64), unique=True)
    media_type: Mapped[str] = mapped_column(String(20))
    bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    message: Mapped[TutorMessage] = relationship(back_populates="attachments")


class LlmCall(Base):
    """Every AI request, for costs, limits and budgets (one ledger for all jobs)."""

    __tablename__ = "llm_calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    learner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job: Mapped[str] = mapped_column(String(20))  # tutor_chat | oral_grading | open_feedback
    provider: Mapped[str] = mapped_column(String(20), default="anthropic")
    model: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(12), default="ok")  # ok | refused | cut_off | imported
    local_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LlmRoute(Base):
    """A family's choice of model for one AI job (otherwise the code default is used)."""

    __tablename__ = "llm_routes"
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), primary_key=True)
    job: Mapped[str] = mapped_column(String(20), primary_key=True)
    model: Mapped[str] = mapped_column(String(60))
    effort: Mapped[str | None] = mapped_column(String(10), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DataImport(Base):
    """A one-off import (e.g. Study data moved from PitchDriven). The same bundle can't be imported twice."""

    __tablename__ = "imports"
    __table_args__ = (UniqueConstraint("bundle_sha256", name="uq_imports_bundle_sha256"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    bundle_sha256: Mapped[str] = mapped_column(String(64))
    counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
