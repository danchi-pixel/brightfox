"""A topic at a glance: runs, the challenge level, the study part, and what needed help.

Nothing here is a score shown to the kid: a run is "new", "started" or "done"; the parent sees which tasks
needed help and what was typed.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..content.checker import LEVELS, goal_list
from ..models import PracticeRun, TaskResult, TopicProgress
from ..timeutil import iso


def levels(t: dict[str, Any]) -> list[int]:
    return [sum(1 for x in t["tasks"] if x["level"] == lv) for lv in LEVELS]


def topic_card(t: dict[str, Any]) -> dict[str, Any]:
    st = t.get("study") or {}
    return {"id": t["id"], "version": t["version"], "subject": t["subject"], "grade": t["grade"], "title": t["title"],
            "intro": t["intro"], "tasks": len(t["tasks"]), "learn": len(t.get("learn", [])), "levels": levels(t),
            "extras": sum(1 for x in t["tasks"] if x.get("extra")), "challenge": len(t.get("challenge", [])),
            "cards": len(st.get("cards", [])), "goals": len(goal_list(st)), "skills": len(t.get("skills", [])),
            "for": t.get("for", []), "has_parent_card": bool(t.get("parent")), "oral": len(t.get("oral", [])),
            "video": len((t.get("video") or {}).get("scenes", []))}


def runs_state(runs: Iterable[PracticeRun]) -> dict[str, Any]:
    """How often the practice itself was done (challenge, review and mock runs are counted elsewhere)."""
    practice = [r for r in runs if r.mode == "practice"]
    return {"runs": len(practice), "finished": sum(1 for r in practice if r.finished),
            "last": iso(max((r.local_date for r in practice), default=None))}


def challenge_state(t: dict[str, Any], runs: Iterable[PracticeRun]) -> dict[str, Any] | None:
    """The "Liga prvakov" level: open once the practice was finished; won (a trophy) once finished itself."""
    if not t.get("challenge"):
        return None
    runs = list(runs)
    return {"tasks": len(t["challenge"]),
            "unlocked": any(r.finished and r.mode == "practice" for r in runs),
            "cleared": any(r.finished and r.mode == "challenge" for r in runs)}


def study_state(t: dict[str, Any], prog: TopicProgress | None) -> dict[str, Any] | None:
    """The study part at a glance: flashcards known, "I can" goals ticked (only what still exists)."""
    st = t.get("study")
    if not st:
        return None
    backs = {c["back"] for c in st.get("cards", [])}
    goals = goal_list(st)
    ids = [g["id"] for g in goals]
    known = [b for b in (prog.known if prog else []) or [] if b in backs]
    ticked = [g for g in ids if g in set((prog.goals if prog else []) or [])]
    return {"cards": len(backs), "known": known, "goals": len(goals), "goal_ids": ids, "ticked": ticked}


def tricky(r: TaskResult) -> bool:
    """Worth another look: not right first time or the solution was needed. An open task always shows its
    solution (the child compares their notebook), so there only "not yet" counts."""
    if r.kind == "open":
        return r.got_it is not True
    return not r.first or r.shown or r.got_it is False


def run_summary(run: PracticeRun | None, task_ids: list[str]) -> dict[str, Any] | None:
    """One run at a glance: when, how many tasks right first time, which needed help (with what was typed)."""
    if run is None:
        return None
    by_task = {r.task_id: r for r in run.results}
    done = [tid for tid in task_ids if tid in by_task]
    hard = [tid for tid in done if tricky(by_task[tid])]
    return {"date": iso(run.local_date), "finished": run.finished, "done": len(done), "total": len(task_ids),
            "first": len(done) - len(hard),
            "tricky": [{"id": tid, "wrong": list(by_task[tid].wrong or [])[:5],
                        "shown": bool(by_task[tid].shown) and by_task[tid].kind != "open",
                        "hints": by_task[tid].hints} for tid in hard]}


def latest(runs: list[PracticeRun], mode: str) -> PracticeRun | None:
    of_mode = [r for r in runs if r.mode == mode]
    return next((r for r in reversed(of_mode) if r.finished), of_mode[-1] if of_mode else None)


def task_totals(runs: list[PracticeRun], task_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Per task over all runs: seen, right first time, solution shown, hints, "not yet", typed mistakes."""
    rows: dict[str, list[TaskResult]] = {tid: [] for tid in task_ids}
    for run in runs:
        for r in run.results:
            if r.task_id in rows:
                rows[r.task_id].append(r)
    out = {}
    for tid, rs in rows.items():
        wrong = list(dict.fromkeys(w for r in reversed(rs) for w in (r.wrong or []) if isinstance(w, str)))
        out[tid] = {"seen": len(rs), "first": sum(1 for r in rs if not tricky(r)), "shown": sum(1 for r in rs if r.shown),
                    "hints": sum(r.hints for r in rs), "not_yet": sum(1 for r in rs if r.got_it is False),
                    "wrong": wrong[:5]}
    return out
