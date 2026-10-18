"""The pure formulas: mastery, readiness, the plan, review boxes and gaps (known inputs → known outputs)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.learning import plan as pl
from app.learning import review as rv
from app.learning.gaps import TopicInput, find_gaps
from app.learning.mastery import Result, label, readiness, topic_mastery

TODAY = date(2026, 10, 18)


def task(i: str, skill: str | None = None, level: int = 1, kind: str = "number") -> dict:
    t = {"id": i, "level": level, "kind": kind, "prompt": f"P{i}", "solution": "S", "answer": 1}
    if skill:
        t["skill"] = skill
    return t


TOPIC = {
    "id": "t", "title": "Ulomki", "version": 1,
    "skills": [{"id": "a", "title": "Del"}, {"id": "b", "title": "Primerjava"}],
    "tasks": [task("a1", "a"), task("a2", "a"), task("b1", "b"), task("b2", "b")],
    "challenge": [task("c1", "a", 3)],
    "study": {"sections": [{"title": "x"}], "cards": [{"front": "f", "back": "k1", "skill": "a"}, {"front": "f", "back": "k2", "skill": "a"}],
              "goals": [{"id": "ga", "text": "A", "skill": "a"}, {"id": "gb", "text": "B", "skill": "b"}]},
}


def good(i: str, d: date = TODAY, run: int = 1) -> Result:
    return Result(i, "number", True, False, None, d, run)


def bad(i: str, d: date = TODAY, run: int = 1) -> Result:
    return Result(i, "number", False, False, None, d, run)


def by_id(skills):
    return {s.skill_id: s for s in skills}


def test_nothing_done_is_not_started():
    m = by_id(topic_mastery(TOPIC, [], [], [], TODAY))
    assert m["a"].mastery is None and m["a"].label == "not_started" and m["a"].tasks == 3


def test_weighted_mastery():
    # Skill a: practice 1/2, challenge 1/1, cards 2/2, goals 1/1 -> (0.4*0.5 + 0.15*1 + 0.1*1 + 0.1*1) / 0.75
    m = by_id(topic_mastery(TOPIC, [good("a1"), bad("a2"), good("c1")], ["k1", "k2"], ["ga"], TODAY))
    assert m["a"].mastery == pytest.approx((0.2 + 0.15 + 0.1 + 0.1) / 0.75)
    assert m["a"].label == "almost"
    # The latest result counts: a2 right later.
    m = by_id(topic_mastery(TOPIC, [bad("a2", run=1), good("a2", run=2), good("a1"), good("c1")], ["k1", "k2"], ["ga"], TODAY))
    assert m["a"].mastery == pytest.approx(1.0) and m["a"].label == "know"


def test_old_results_count_half():
    old = TODAY - timedelta(days=40)
    m = by_id(topic_mastery(TOPIC, [good("b1", old), good("b2", old)], [], [], TODAY))
    # Skill b: practice 1/2 (two half-counts), goals 0/1 -> (0.4*0.5 + 0.1*0) / 0.5
    assert m["b"].mastery == pytest.approx(0.4)


def test_self_report_only():
    # Untried tasks count as 0: cards 2/2 and goal 1/1 alone -> (0.1 + 0.1) / 0.75.
    m = by_id(topic_mastery(TOPIC, [], ["k1", "k2"], ["ga"], TODAY))
    assert m["a"].mastery == pytest.approx(0.2 / 0.75)
    # A skill with only flashcards and goals (no tasks) is capped at 60 %: "Znam" needs shown work.
    words = {**TOPIC, "skills": TOPIC["skills"] + [{"id": "w", "title": "Besede"}],
             "study": {"sections": [{"title": "x"}], "cards": [{"front": "f", "back": "w1", "skill": "w"}],
                       "goals": [{"id": "gw", "text": "W", "skill": "w"}]}}
    m = by_id(topic_mastery(words, [], ["w1"], ["gw"], TODAY))
    assert m["w"].mastery == pytest.approx(0.6) and m["w"].label == "almost"


def test_topic_without_skills_is_one_skill():
    t = {"id": "x", "title": "X", "tasks": [task("1"), task("2")]}
    [s] = topic_mastery(t, [good("1")], [], [], TODAY)
    assert s.skill_id == "_topic" and s.mastery == pytest.approx(0.5)


def test_readiness_and_labels():
    skills = topic_mastery(TOPIC, [good("a1"), good("a2"), good("c1")], ["k1", "k2"], ["ga"], TODAY)
    # a = 1.0 (3 tasks), b = untouched (2 tasks) -> 3/5 = 0.6
    assert readiness(skills) == 0.6
    assert readiness(topic_mastery(TOPIC, [], [], [], TODAY)) is None
    assert [label(x) for x in (None, 0.2, 0.5, 0.79, 0.8)] == ["not_started", "not_yet", "almost", "almost", "know"]


def test_review_boxes():
    assert rv.after_answer(1, False, TODAY) == (1, TODAY + timedelta(days=1), False)
    assert rv.after_answer(1, True, TODAY) == (2, TODAY + timedelta(days=3), False)
    assert rv.after_answer(3, True, TODAY) == (4, TODAY + timedelta(days=14), False)
    assert rv.after_answer(4, True, TODAY)[2] is True
    assert rv.after_answer(4, False, TODAY)[0] == 1


def skill_in(skill: str, mastery, share=0.0, cards=0) -> pl.SkillInput:
    return pl.SkillInput("t", "Ulomki", skill, skill.upper(), mastery, share, True, cards, True, False)


def test_plan_weakest_first_and_light_last_day():
    exam = TODAY + timedelta(days=4)  # Wed (today is Sunday 18 Oct) -> study days Sun..Tue
    p = pl.build_plan(TODAY, exam, [1, 2, 3, 4, 5, 6, 7], 20, [skill_in("a", 0.7, 0.5), skill_in("b", None, 0.0, cards=3)],
                      review_due=2, has_mock=False, done_today={"review::"})
    days = p["days"]
    assert [d["date"] for d in days] == [(TODAY + timedelta(days=i)).isoformat() for i in range(4)]
    first = days[0]["steps"]
    assert first[0]["kind"] == "review" and first[0]["done"] is True
    assert first[1]["skill_id"] == "b" and first[1]["kind"] == "learn"  # weakest (not started) first
    last = days[-1]["steps"]
    assert [s["kind"] for s in last] == ["review", "learn"] and last[1]["skill_id"] == "b"
    assert p["too_little_time"] is False


def test_plan_never_leaves_a_day_empty():
    exam = TODAY + timedelta(days=5)
    p = pl.build_plan(TODAY, exam, None, 30, [skill_in("a", 0.9, 0.9)], 0, False, set())
    assert all(d["steps"] for d in p["days"])


def test_plan_follows_rhythm_and_flags_too_little_time():
    exam = TODAY + timedelta(days=3)
    many = [skill_in(f"s{i}", None, 0.0, cards=5) for i in range(6)]
    p = pl.build_plan(TODAY, exam, [3], 10, many, 0, False, set())  # only Wednesdays, but today is always a day
    assert [d["date"] for d in p["days"]] == [TODAY.isoformat()]
    assert p["too_little_time"] is True
    assert pl.build_plan(TODAY, TODAY, None, 20, many, 0, False, set())["days"] == []


def test_gaps_find_the_right_things():
    results = [bad("a1", run=1), bad("a1", run=2), Result("b1", "number", True, True, None, TODAY, 2)]
    skills = topic_mastery(TOPIC, results, ["k1"], [], TODAY)
    ti = TopicInput(TOPIC, skills, results, {"a1": ["3/4", "4/3"]}, ["k1"], [], exam_days_left=5)
    g = find_gaps([ti], overdue_reviews=2, today=TODAY)
    sev = [(x["severity"], x["title"]) for x in g]
    assert ("critical", "Pa1") in sev and g[0]["severity"] == "critical"
    assert next(x for x in g if x["title"] == "Pa1")["wrong"] == ["3/4", "4/3"]
    assert any(x["severity"] == "critical" and x["skill_id"] == "a" for x in g)  # on the test in 5 days, below 50 %
    assert ("minor", "Pb1") in sev  # needed the solution
    assert any(x["action"] == "review" for x in g)
