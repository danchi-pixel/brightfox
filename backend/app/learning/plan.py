"""The step-by-step plan up to a test. Recomputed every day from the learner's current mastery (nothing is
stored), so a good day moves the plan forward by itself and a missed day is simply absorbed.

Weakest skills first. Per skill: 📖 read the notes (if it's not started or weak), 🃏 flashcards (if some
aren't known), ✏️ practice (until 80 %), then 🏆 the Champions League. Moje napake first on any day they're
due. The day before the test is light: Moje napake and a recap of the weakest skill. A mock test (when the
test has one) goes on the second-to-last study day.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

MINUTES = {"learn": 8, "cards": 5, "practice": 10, "challenge": 10, "review": 5, "mock": 30}


@dataclass
class SkillInput:
    topic_id: str
    topic_title: str
    skill_id: str
    title: str
    mastery: float | None
    practice_share: float  # share of practice tasks right first time (latest result)
    has_study: bool
    cards_left: int
    has_challenge: bool
    challenge_cleared: bool


@dataclass
class Step:
    kind: str  # learn | cards | practice | challenge | review | mock
    topic_id: str | None = None
    skill_id: str | None = None
    title: str = ""
    minutes: int = 0
    done: bool = False

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.topic_id or ''}:{self.skill_id or ''}"

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "kind": self.kind, "topic_id": self.topic_id, "skill_id": self.skill_id,
                "title": self.title, "minutes": self.minutes, "done": self.done}


@dataclass
class Day:
    date: date
    steps: list[Step] = field(default_factory=list)

    @property
    def minutes(self) -> int:
        return sum(s.minutes for s in self.steps)


def study_days(today: date, exam_date: date, rhythm_days: list[int] | None) -> list[date]:
    """Today (when before the test) and the learner's usual study days up to the day before the test."""
    days = [today + timedelta(days=i) for i in range((exam_date - today).days)]
    if not days:
        return []
    usual = set(rhythm_days or [1, 2, 3, 4, 5, 6, 7])
    picked = [d for d in days if d == today or d.isoweekday() in usual]
    return picked or days


def skill_steps(s: SkillInput) -> list[Step]:
    steps = []
    if s.has_study and (s.mastery is None or s.mastery < 0.5):
        steps.append(Step("learn", s.topic_id, s.skill_id, s.title, MINUTES["learn"]))
    if s.cards_left > 0:
        steps.append(Step("cards", s.topic_id, s.skill_id, s.title, MINUTES["cards"]))
    if s.practice_share < 0.8:
        steps.append(Step("practice", s.topic_id, s.skill_id, s.title, MINUTES["practice"]))
    elif s.has_challenge and not s.challenge_cleared:
        steps.append(Step("challenge", s.topic_id, s.skill_id, s.title, MINUTES["challenge"]))
    return steps


def build_plan(today: date, exam_date: date, rhythm_days: list[int] | None, minutes_per_day: int,
               skills: list[SkillInput], review_due: int, has_mock: bool, done_today: set[str],
               mock_id: str | None = None, mock_title: str = "Poskusni test") -> dict[str, Any]:
    days = [Day(d) for d in study_days(today, exam_date, rhythm_days)]
    if not days:
        return {"days": [], "too_little_time": False, "remaining": 0}
    ordered = sorted(skills, key=lambda s: -1.0 if s.mastery is None else s.mastery)
    work = [st for s in ordered for st in skill_steps(s)]
    weakest = ordered[0] if ordered else None

    # Fixed points: Moje napake today, the light last day, the mock on the second-to-last day.
    if review_due:
        days[0].steps.append(Step("review", title="Moje napake", minutes=MINUTES["review"]))
    last = days[-1] if len(days) > 1 else None
    if last is not None:
        last.steps.append(Step("review", title="Moje napake", minutes=MINUTES["review"]))
        if weakest is not None and weakest.has_study:
            last.steps.append(Step("learn", weakest.topic_id, weakest.skill_id, weakest.title, MINUTES["learn"]))
    if has_mock:
        # The mock step carries the mock's id where topic steps carry the topic's.
        (days[-2] if len(days) > 2 else days[-1]).steps.append(Step("mock", mock_id, None, mock_title, MINUTES["mock"]))

    # Fill the other days in order, up to the daily minutes (at least one step a day).
    fill = [d for d in days if d is not last] or days
    i = 0
    for day in fill:
        while i < len(work) and (not day.steps or day.minutes + work[i].minutes <= minutes_per_day):
            day.steps.append(work[i])
            i += 1
    remaining = len(work) - i
    if remaining:
        # Not enough time: the rest goes onto the days anyway (the parent sees "too little time").
        for j, st in enumerate(work[i:]):
            fill[j % len(fill)].steps.append(st)
    # Days left empty (little left to learn): another round of practice on the weakest skill keeps it fresh.
    for day in fill:
        if not day.steps and weakest is not None:
            day.steps.append(Step("practice", weakest.topic_id, weakest.skill_id, weakest.title, MINUTES["practice"]))
    for st in days[0].steps:
        st.done = st.key in done_today or (st.kind in ("learn", "cards", "practice", "challenge") and
                                           f"{st.kind}:{st.topic_id}:" in done_today)
    return {"days": [{"date": d.date.isoformat(), "minutes": d.minutes, "steps": [s.as_dict() for s in d.steps]} for d in days],
            "too_little_time": remaining > 0, "remaining": remaining}
