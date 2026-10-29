"""One independently saved learning-bank state per learner and topic."""
from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base
from .study import _learner_fk


class LabProgress(Base):
    __tablename__ = "lab_progress"
    __table_args__ = (_learner_fk("lab_progress"),)
    family_id: Mapped[int] = mapped_column(Integer)
    learner_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
