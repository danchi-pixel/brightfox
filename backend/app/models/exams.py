"""Tests at school and Moje napake (spaced review of mistakes)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow


class Exam(Base):
    """A test at school a parent entered: the date, what's on it, the grade they aim for."""

    __tablename__ = "exams"
    __table_args__ = (ForeignKeyConstraint(["family_id", "learner_id"], ["learners.family_id", "learners.id"],
                                           ondelete="CASCADE", name="fk_exams_learner"),
                      Index("ix_exams_learner_date", "learner_id", "exam_date"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, index=True)
    learner_id: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(80))
    exam_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(10), default="written")  # written | oral
    target_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 2–5 (Slovenian grades)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # what the teacher said is on it
    result_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)  # filled in afterwards
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    scope: Mapped[list[ExamScope]] = relationship(back_populates="exam", cascade="all, delete-orphan", order_by="ExamScope.id")


class ExamScope(Base):
    """A topic (or one skill of it) that is on the test."""

    __tablename__ = "exam_scope"
    __table_args__ = (UniqueConstraint("exam_id", "topic_id", "skill_id", name="uq_exam_scope_item"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(String(80))
    skill_id: Mapped[str] = mapped_column(String(40), default="")  # "" = the whole topic
    exam: Mapped[Exam] = relationship(back_populates="scope")


class ReviewItem(Base):
    """Moje napake: a task that needed help, coming back after 1, 3, 7 and 14 days until it's right first time
    four times in a row; then it's "popravljeno" (corrected) for good."""

    __tablename__ = "review_items"
    __table_args__ = (ForeignKeyConstraint(["family_id", "learner_id"], ["learners.family_id", "learners.id"],
                                           ondelete="CASCADE", name="fk_review_items_learner"),
                      UniqueConstraint("learner_id", "topic_id", "item_kind", "item_id", name="uq_review_items_item"),
                      Index("ix_review_items_learner_due", "learner_id", "due_date"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, index=True)
    learner_id: Mapped[int] = mapped_column(Integer)
    topic_id: Mapped[str] = mapped_column(String(80))
    item_kind: Mapped[str] = mapped_column(String(10), default="task")
    item_id: Mapped[str] = mapped_column(String(40))
    skill_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    box: Mapped[int] = mapped_column(Integer, default=1)  # 1..4
    due_date: Mapped[date] = mapped_column(Date)
    wrong: Mapped[str | None] = mapped_column(String(100), nullable=True)  # the last thing typed wrong
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
