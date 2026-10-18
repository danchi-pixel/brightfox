"""Knowledge gaps: what a learner still misses, worst first, each with its reasons and the typed mistakes.

critical   a skill on a test within 10 days below 50 %; a task wrong in two or more runs
attention  a skill on a test at 50–79 %; Moje napake overdue by more than 3 days; 3+ flashcards not known
           in a topic the learner started on
minor      an "I can" goal not ticked although its tasks went well; the solution was looked at
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .mastery import Result, SkillMastery, is_good

SEVERITY = {"critical": 0, "attention": 1, "minor": 2}


@dataclass
class Gap:
    severity: str
    topic_id: str
    topic_title: str
    skill_id: str | None
    title: str
    reasons: list[str] = field(default_factory=list)
    wrong: list[str] = field(default_factory=list)
    action: str = "practice"  # practice | learn | cards | review | goals

    def as_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "topic_id": self.topic_id, "topic_title": self.topic_title,
                "skill_id": self.skill_id, "title": self.title, "reasons": self.reasons, "wrong": self.wrong[:5],
                "action": self.action}


@dataclass
class TopicInput:
    topic: dict[str, Any]
    skills: list[SkillMastery]
    results: list[Result]
    wrong_by_task: dict[str, list[str]]
    known: list[str]
    ticked: list[str]
    exam_days_left: int | None  # the nearest test with this topic in scope, if any


def find_gaps(topics: list[TopicInput], overdue_reviews: int, today: date) -> list[dict[str, Any]]:
    out: list[Gap] = []
    for ti in topics:
        t = ti.topic
        # Skills on an upcoming test.
        if ti.exam_days_left is not None:
            for s in ti.skills:
                m = s.mastery or 0.0
                if m < 0.5 and ti.exam_days_left <= 10:
                    out.append(Gap("critical", t["id"], t["title"], s.skill_id, s.title,
                                   [f"On the test in {ti.exam_days_left} days, about {round(m * 100)} % ready"],
                                   action="learn" if s.mastery is None else "practice"))
                elif m < 0.8:
                    out.append(Gap("attention", t["id"], t["title"], s.skill_id, s.title,
                                   [f"On a test, about {round(m * 100)} % ready"]))
        # The same task wrong in two or more runs.
        runs_bad: dict[str, set[int]] = defaultdict(set)
        shown: set[str] = set()
        for r in ti.results:
            if not is_good(r):
                runs_bad[r.task_id].add(r.run_id)
            if r.shown and r.kind != "open":
                shown.add(r.task_id)
        tasks = {x["id"]: x for x in t["tasks"] + t.get("challenge", [])}
        for task_id, runs in runs_bad.items():
            if len(runs) >= 2 and task_id in tasks:
                out.append(Gap("critical", t["id"], t["title"], tasks[task_id].get("skill"), tasks[task_id]["prompt"][:80],
                               [f"Wrong in {len(runs)} runs"], ti.wrong_by_task.get(task_id, [])))
        # Flashcards not known in a topic the learner started on.
        cards = [c["back"] for c in (t.get("study") or {}).get("cards", [])]
        unknown = [c for c in cards if c not in set(ti.known)]
        if ti.known and len(unknown) >= 3:
            out.append(Gap("attention", t["id"], t["title"], None, f"{len(unknown)} flashcards", [f"Not known yet: {', '.join(unknown[:6])}"],
                           action="cards"))
        # Goals not ticked although the practice went well; solutions looked at.
        good_practice = all((s.parts.get("practice", {}).get("done", 0) / max(s.parts.get("practice", {}).get("total", 1), 1)) >= 0.8
                            for s in ti.skills if s.mastery is not None) and any(s.mastery is not None for s in ti.skills)
        goals = (t.get("study") or {}).get("goals", [])
        if goals and good_practice and len(ti.ticked) < len(goals):
            out.append(Gap("minor", t["id"], t["title"], None, '"I can" goals', ["The practice went well, but not every goal is ticked"],
                           action="goals"))
        for task_id in shown - {k for k, v in runs_bad.items() if len(v) >= 2}:
            if task_id in tasks:
                out.append(Gap("minor", t["id"], t["title"], tasks[task_id].get("skill"), tasks[task_id]["prompt"][:80],
                               ["Needed the solution"], ti.wrong_by_task.get(task_id, [])))
    if overdue_reviews:
        out.append(Gap("attention", "", "Moje napake", None, "Moje napake", [f"{overdue_reviews} overdue by more than 3 days"],
                       action="review"))
    out.sort(key=lambda g: SEVERITY[g.severity])
    return [g.as_dict() for g in out]
