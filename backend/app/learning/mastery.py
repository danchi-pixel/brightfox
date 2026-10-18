"""Mastery per skill and readiness for a test (docs/readiness.md explains it for parents).

A skill's mastery is a weighted share of evidence:

    Vaja (the practice tasks)    40 %   tasks whose latest result was right first time without the solution
    Poskusni test (mock)         25 %   (Phase 5; left out until mocks exist)
    Liga prvakov (challenge)     15 %   the same, on the hard level
    Kartice (flashcards)         10 %   cards marked "znam"
    Kaj znam (goals)             10 %   goals ticked

Parts with nothing in the topic are left out and the rest re-weighted; tasks never tried count as 0. A right
result older than 28 days counts half. With only self-reported evidence (cards and goals, no task tried) a
skill is capped at 60 %: "Znam" needs shown work. Topics without skills count as one skill, "_topic".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from ..content.checker import goal_list

WEIGHTS = {"practice": 0.40, "mock": 0.25, "challenge": 0.15, "cards": 0.10, "goals": 0.10}
OLD_DAYS = 28
SELF_REPORT_CAP = 0.60
WHOLE = "_topic"


def label(mastery: float | None) -> str:
    if mastery is None:
        return "not_started"
    if mastery >= 0.80:
        return "know"
    if mastery >= 0.50:
        return "almost"
    return "not_yet"


@dataclass
class Result:
    """The fields of a task result that mastery needs (TaskResult rows or plain test data)."""

    task_id: str
    kind: str
    first: bool
    shown: bool
    got_it: bool | None
    local_date: date
    run_id: int = 0


def is_good(r: Result) -> bool:
    if r.kind == "open":
        return r.got_it is True
    return r.first and not r.shown and r.got_it is not False


@dataclass
class SkillMastery:
    skill_id: str
    title: str
    tasks: int  # practice + challenge tasks in this skill (the weight in readiness)
    mastery: float | None
    label: str
    parts: dict[str, dict[str, float]] = field(default_factory=dict)  # part -> {done, total}

    def as_dict(self) -> dict[str, Any]:
        return {"skill_id": self.skill_id, "title": self.title, "tasks": self.tasks,
                "mastery": None if self.mastery is None else round(self.mastery, 3), "label": self.label,
                "parts": {k: {"done": round(v["done"], 2), "total": int(v["total"])} for k, v in self.parts.items()}}


def skills_of(topic: dict[str, Any]) -> list[tuple[str, str]]:
    skills = [(s["id"], s["title"]) for s in topic.get("skills", [])]
    return skills or [(WHOLE, topic["title"])]


def _skill(obj: dict[str, Any], has_skills: bool) -> str:
    return obj.get("skill") or WHOLE if has_skills else WHOLE


def topic_mastery(topic: dict[str, Any], results: Iterable[Result], known: list[str], ticked: list[str],
                  today: date, mock_scores: dict[str, tuple[float, float]] | None = None) -> list[SkillMastery]:
    """Mastery of every skill of a topic for one learner. ``mock_scores``: skill -> (points, max points)."""
    has_skills = bool(topic.get("skills"))
    latest: dict[str, Result] = {}
    for r in sorted(results, key=lambda x: (x.local_date, x.run_id)):
        latest[r.task_id] = r
    parts: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"done": 0.0, "total": 0.0}))
    tried: dict[str, bool] = defaultdict(bool)
    task_count: dict[str, int] = defaultdict(int)

    for part, tasks in (("practice", topic["tasks"]), ("challenge", topic.get("challenge", []))):
        for t in tasks:
            sk = _skill(t, has_skills)
            task_count[sk] += 1
            parts[sk][part]["total"] += 1
            r = latest.get(t["id"])
            if r is not None:
                tried[sk] = True
                if is_good(r):
                    parts[sk][part]["done"] += 0.5 if (today - r.local_date).days > OLD_DAYS else 1.0
    study = topic.get("study") or {}
    known_set = set(known)
    for card in study.get("cards", []):
        sk = _skill(card, has_skills)
        parts[sk]["cards"]["total"] += 1
        parts[sk]["cards"]["done"] += 1.0 if card["back"] in known_set else 0.0
    ticked_set = set(ticked)
    for g in goal_list(study):
        sk = _skill(g, has_skills)
        parts[sk]["goals"]["total"] += 1
        parts[sk]["goals"]["done"] += 1.0 if g["id"] in ticked_set else 0.0
    for sk, (pts, mx) in (mock_scores or {}).items():
        if mx > 0:
            parts[sk]["mock"]["total"] = 1.0
            parts[sk]["mock"]["done"] = pts / mx
            tried[sk] = True

    out = []
    for sk, title in skills_of(topic) + ([(WHOLE, topic["title"])] if has_skills and WHOLE in parts else []):
        p = parts.get(sk, {})
        present = {k: v for k, v in p.items() if v["total"] > 0}
        evidence = any(v["done"] > 0 for v in present.values()) or tried[sk]
        if not present or not evidence:
            out.append(SkillMastery(sk, title, task_count[sk], None, label(None), dict(present)))
            continue
        wsum = sum(WEIGHTS[k] for k in present)
        m = sum(WEIGHTS[k] * (v["done"] / v["total"]) for k, v in present.items()) / wsum
        if not tried[sk]:
            m = min(m, SELF_REPORT_CAP)
        out.append(SkillMastery(sk, title, task_count[sk], m, label(m), dict(present)))
    return out


def readiness(skills: list[SkillMastery]) -> float | None:
    """A test's readiness: the skills' mastery weighted by their number of tasks (untouched skills count as 0),
    rounded to 5 %. None when nothing in scope has been started."""
    if not skills or all(s.mastery is None for s in skills):
        return None
    weights = [max(s.tasks, 1) for s in skills]
    value = sum(w * (s.mastery or 0.0) for w, s in zip(weights, skills)) / sum(weights)
    return round(value * 20) / 20
