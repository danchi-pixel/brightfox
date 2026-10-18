"""Topics: load and check them.

A topic is one JSON file (format in docs/content-format.md), written by Claude Code from photos of what a
child is learning: a study part (📖 Uči se: notes, flashcards, "I can" goals), practice tasks from easy to
harder with hints and worked solutions (✏️ Vaja), and an optional harder level (🏆 Liga prvakov). ``load``
checks everything (answers that can be checked, unique ids, a solution for every task, gender-neutral
"you" in Slovene) so a broken file can't reach a child. A topic reaches a learner only after a parent
approved its current ``version`` for them.

Folders: ``data/global/topics`` (offered to every family) and ``data/families/<slug>/topics`` (one family
only). Ids are unique across all folders. Check the files by hand with
``backend\\.venv\\Scripts\\python.exe -m app.content.checker``.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
SUBJECTS = ("math", "slovene", "english", "science", "society", "other")
KINDS = ("choice", "number", "text", "open")
LEVELS = (1, 2, 3)  # 1 warm-up, 2 practice, 3 challenge
GRADES = range(1, 14)  # 1–9 primary school (razred), 10–13 secondary school (1.–4. letnik)
ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,78}")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
TASK_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")

_INT = re.compile(r"[-+]?\d+")
_DEC = re.compile(r"[-+]?\d+,\d+")  # decimal comma, as in Slovenian schools
_FRAC = re.compile(r"([-+]?)(\d+)/(\d+)")
_MIXED = re.compile(r"([-+]?)(\d+) (\d+)/(\d+)")

# Gendered "you" in Slovene: "si naredil", "boš pripravljena", "bi rad" ... Kid-facing text addresses the
# child with imperatives and the present tense instead. Characters in stories ("Luka je igral") are fine.
_GENDERED_YOU = re.compile(
    r"\b(si|boš|bi|nisi|ne boš)\s+(\w+(?:il|ila|al|ala|el|ela|ul|ula|ol|ola|rl|rla)|"
    r"pripravljen\w*|vesel\w*|ponosen|ponosna|rad|rada|sam|sama|zadovoljen|zadovoljna|utrujen\w*)\b",
    re.IGNORECASE)


class ContentError(ValueError):
    """The content files have problems (all of them are listed in the message)."""


def parse_answer(value: Any) -> Fraction | None:
    """The exact value of a number answer in a topic file: 12, -3, 2.5, "2,5", "3/4" or "1 3/4".

    Written answers use the decimal comma; a decimal point in a text ("2.5") is refused because in Slovenian
    "2.500" means two thousand five hundred. (The browser accepts more ways of typing.)
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))
    if not isinstance(value, str):
        return None
    s = value.strip()
    if _INT.fullmatch(s):
        return Fraction(int(s))
    if _DEC.fullmatch(s):
        return Fraction(s.replace(",", "."))
    if m := _MIXED.fullmatch(s):
        sign, whole, num, den = m.groups()
        if int(den) == 0:
            return None
        v = int(whole) + Fraction(int(num), int(den))
        return -v if sign == "-" else v
    if m := _FRAC.fullmatch(s):
        sign, num, den = m.groups()
        if int(den) == 0:
            return None
        v = Fraction(int(num), int(den))
        return -v if sign == "-" else v
    return None


@dataclass(frozen=True)
class Content:
    topics: dict[str, dict[str, Any]]  # id -> topic (as in the file, plus nothing)
    scope: dict[str, str]  # id -> "global" or a family slug (topics and mocks)
    order: tuple[str, ...]  # newest first (files are named so they sort by date)
    mocks: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> mock test
    mock_order: tuple[str, ...] = ()

    def for_family(self, slug: str) -> list[str]:
        """The topics a family may see: global ones and its own, newest first."""
        return [i for i in self.order if self.scope[i] in ("global", slug)]

    def mocks_for_family(self, slug: str) -> list[str]:
        return [i for i in self.mock_order if self.scope[i] in ("global", slug)]


@dataclass
class _Checker:
    problems: list[str] = field(default_factory=list)

    def bad(self, where: str, msg: str) -> None:
        self.problems.append(f"{where}: {msg}")

    def text(self, obj: dict, key: str, where: str, optional: bool = False, limit: int = 400) -> None:
        if key not in obj:
            if not optional:
                self.bad(where, f"\"{key}\" is required")
            return
        v = obj[key]
        if not isinstance(v, str) or not v.strip():
            self.bad(where, f"\"{key}\" must be a non-empty text")
        elif len(v) > limit:
            self.bad(where, f"\"{key}\" is too long ({len(v)} > {limit} characters)")

    def texts(self, obj: dict, key: str, where: str, lo: int, hi: int, limit: int) -> None:
        v = obj.get(key, [])
        if not isinstance(v, list) or not lo <= len(v) <= hi:
            self.bad(where, f"\"{key}\" must list {lo}–{hi} texts")
            return
        for i, t in enumerate(v):
            if not isinstance(t, str) or not t.strip():
                self.bad(where, f"\"{key}\"[{i}] must be a non-empty text")
            elif len(t) > limit:
                self.bad(where, f"\"{key}\"[{i}] is too long ({len(t)} > {limit} characters)")

    def only(self, obj: dict, allowed: set[str], where: str) -> None:
        extra = set(obj) - allowed
        if extra:
            self.bad(where, f"unknown field(s): {', '.join(sorted(extra))}")

    def objects(self, obj: dict, key: str, where: str, lo: int, hi: int) -> list[dict]:
        v = obj.get(key, [])
        if not isinstance(v, list) or not lo <= len(v) <= hi or not all(isinstance(x, dict) for x in v):
            self.bad(where, f"\"{key}\" must list {lo}–{hi} items")
            return []
        return v

    def skill(self, obj: dict, where: str, skills: set[str]) -> None:
        if "skill" in obj and obj["skill"] not in skills:
            self.bad(where, f"unknown skill {obj['skill']!r} (list it in \"skills\")")


def _kid_texts(t: Any) -> list[str]:
    """Every text in a topic part (for the gendered-"you" check)."""
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [s for x in t for s in _kid_texts(x)]
    if isinstance(t, dict):
        return [s for k, x in t.items() if k not in ("say",) for s in _kid_texts(x)]
    return []


def _check_task(c: _Checker, t: dict, w: str, skills: set[str]) -> None:
    kind = t.get("kind")
    c.only(t, {"id", "level", "kind", "prompt", "options", "answer", "accept", "exact", "unit", "hints", "solution",
               "extra", "say", "skill", "traps"}, w)
    # "say": English the browser reads aloud (a listen button), e.g. for dictation.
    c.text(t, "say", w, optional=True, limit=200)
    c.skill(t, w, skills)
    if t.get("level") not in LEVELS:
        c.bad(w, "\"level\" must be 1 (warm-up), 2 (practice) or 3 (challenge)")
    if kind not in KINDS:
        c.bad(w, f"\"kind\" must be one of {', '.join(KINDS)}")
    c.text(t, "prompt", w, limit=600)
    c.text(t, "solution", w, limit=1200)
    c.texts(t, "hints", w, 0, 3, 300)
    if "extra" in t and not isinstance(t["extra"], bool):
        c.bad(w, "\"extra\" must be true or false (true = a bonus task beyond the book)")
    # "traps": known wrong answers with a short reason, shown when the child types exactly that.
    for i, trap in enumerate(c.objects(t, "traps", w, 0, 4) if "traps" in t else []):
        tw = f"{w}.traps[{i}]"
        c.only(trap, {"answer", "why"}, tw)
        c.text(trap, "answer", tw, limit=120)
        c.text(trap, "why", tw, limit=200)
    if kind == "choice":
        c.texts(t, "options", w, 2, 6, 200)
        opts = t.get("options") if isinstance(t.get("options"), list) else []
        a = t.get("answer")
        if not isinstance(a, int) or isinstance(a, bool) or not 0 <= a < len(opts):
            c.bad(w, f"\"answer\" must be the number of the right option, counted from 0 (0–{max(len(opts) - 1, 0)})")
        # Case counts: "english" vs "English" can be the whole point of a task.
        elif len({o.strip() for o in opts if isinstance(o, str)}) != len(opts):
            c.bad(w, "two options are the same")
    elif kind == "number":
        if parse_answer(t.get("answer")) is None:
            c.bad(w, "\"answer\" must be a number: 12, -3, 2.5 (JSON number), \"2,5\", \"3/4\" or \"1 3/4\"")
        c.text(t, "unit", w, optional=True, limit=12)
    elif kind == "text":
        c.text(t, "answer", w, limit=120)
        if "accept" in t:
            c.texts(t, "accept", w, 1, 10, 120)
        if "exact" in t and not isinstance(t["exact"], bool):
            c.bad(w, "\"exact\" must be true or false (true = č, š and ž must be right too)")
    elif kind == "open" and "answer" in t:
        c.bad(w, "an open task has no \"answer\" (the child compares their work with the solution)")
    if kind != "choice" and "options" in t:
        c.bad(w, "only a choice task has \"options\"")
    if kind != "text" and ("accept" in t or "exact" in t):
        c.bad(w, "only a text task has \"accept\" and \"exact\"")
    if kind != "number" and "unit" in t:
        c.bad(w, "only a number task has \"unit\"")


def goal_list(study: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The "I can" goals as {id, text, skill}: format-1 files list plain texts, which get ids g0, g1, ..."""
    out = []
    for i, g in enumerate((study or {}).get("goals", [])):
        out.append({"id": f"g{i}", "text": g} if isinstance(g, str) else {**g})
    return out


def _check_study(c: _Checker, st: Any, w: str, skills: set[str]) -> None:
    """The study part ("Uči se"): notes in sections, flashcards and an "I can" checklist."""
    if not isinstance(st, dict):
        c.bad(w, "\"study\" must be {goals, sections, cards}")
        return
    c.only(st, {"goals", "sections", "cards"}, w)
    goals = st.get("goals", [])
    if not isinstance(goals, list) or not 0 <= len(goals) <= 8 or ("goals" in st and not goals):
        c.bad(w, "\"goals\" must list 1–8 goals")
        goals = []
    goal_ids: set[str] = set()
    for i, g in enumerate(goals):
        gw = f"{w}.goals[{i}]"
        if isinstance(g, str):
            if not g.strip() or len(g) > 120:
                c.bad(gw, "a goal is a short text (≤120 characters)")
            continue
        if not isinstance(g, dict):
            c.bad(gw, "a goal is a text or {id, text, skill}")
            continue
        c.only(g, {"id", "text", "skill"}, gw)
        c.text(g, "text", gw, limit=120)
        c.skill(g, gw, skills)
        gid = g.get("id")
        if not isinstance(gid, str) or not TASK_ID_RE.fullmatch(gid) or gid in goal_ids:
            c.bad(gw, f"goal id {gid!r} must be unique (a-z, 0-9 and -)")
        goal_ids.add(str(gid))
    if any(isinstance(g, str) for g in goals) and any(isinstance(g, dict) for g in goals):
        c.bad(w, "goals are either all texts or all {id, text}")
    sections = st.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= 12 or not all(isinstance(x, dict) for x in sections):
        c.bad(w, "\"sections\" must list 1–12 sections")
        sections = []
    for i, sec in enumerate(sections):
        sw = f"{w}.sections[{i}]"
        c.only(sec, {"title", "text", "table", "examples", "watch_out", "skill"}, sw)
        c.text(sec, "title", sw, limit=60)
        c.text(sec, "text", sw, optional=True, limit=800)
        c.skill(sec, sw, skills)
        if "examples" in sec:
            c.texts(sec, "examples", sw, 1, 8, 200)
        if "table" in sec:
            t = sec["table"]
            if not isinstance(t, dict):
                c.bad(sw, "\"table\" must be {head, rows}")
            else:
                c.only(t, {"head", "rows", "say"}, f"{sw}.table")
                head = t.get("head")
                rows = t.get("rows")
                # "say": the columns read aloud by the row's listen button (the English ones), e.g. [0, 1].
                say = t.get("say", [])
                if not isinstance(say, list) or not all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(head or []) for i in say):
                    c.bad(f"{sw}.table", "\"say\" must list column numbers, counted from 0")
                if not isinstance(head, list) or not 2 <= len(head) <= 4 or not all(isinstance(h, str) and h.strip() for h in head):
                    c.bad(f"{sw}.table", "\"head\" must list 2–4 column titles")
                elif (not isinstance(rows, list) or not 1 <= len(rows) <= 40
                      or not all(isinstance(r, list) and len(r) == len(head) and all(isinstance(x, str) and len(x) <= 80 for x in r) for r in rows)):
                    c.bad(f"{sw}.table", f"\"rows\" must list 1–40 rows of {len(head)} short texts")
        for j, wo in enumerate(sec.get("watch_out", []) if isinstance(sec.get("watch_out", []), list) else [None]):
            ww = f"{sw}.watch_out[{j}]"
            if not isinstance(wo, dict):
                c.bad(ww, "must be {wrong, right, why}")
                continue
            c.only(wo, {"wrong", "right", "why"}, ww)
            c.text(wo, "wrong", ww, limit=120)
            c.text(wo, "right", ww, limit=120)
            c.text(wo, "why", ww, optional=True, limit=200)
        if "watch_out" in sec and (not isinstance(sec["watch_out"], list) or not 1 <= len(sec["watch_out"]) <= 6):
            c.bad(sw, "\"watch_out\" must list 1–6 mistakes")
    cards = st.get("cards", [])
    if not isinstance(cards, list) or len(cards) > 80 or not all(isinstance(x, dict) for x in cards):
        c.bad(w, "\"cards\" must list 0–80 flashcards")
        cards = []
    backs: set[str] = set()
    for i, card in enumerate(cards):
        cw = f"{w}.cards[{i}]"
        c.only(card, {"front", "back", "skill"}, cw)
        c.text(card, "front", cw, limit=80)
        c.text(card, "back", cw, limit=80)
        c.skill(card, cw, skills)
        back = str(card.get("back", "")).strip().lower()
        if back in backs:
            c.bad(cw, f"two cards have the same back {card.get('back')!r} (it's the card's id)")
        backs.add(back)


def _check_parent(c: _Checker, p: Any, w: str) -> None:
    """The parent helper card: how school teaches it, typical mistakes, questions for the car."""
    if not isinstance(p, dict):
        c.bad(w, "\"parent\" must be {school_method, typical_mistakes, car_questions, tips}")
        return
    c.only(p, {"school_method", "typical_mistakes", "car_questions", "tips"}, w)
    c.text(p, "school_method", w, optional=True, limit=800)
    if "typical_mistakes" in p:
        c.texts(p, "typical_mistakes", w, 1, 6, 200)
    if "tips" in p:
        c.texts(p, "tips", w, 1, 5, 200)
    for i, q in enumerate(c.objects(p, "car_questions", w, 1, 8) if "car_questions" in p else []):
        qw = f"{w}.car_questions[{i}]"
        c.only(q, {"q", "a"}, qw)
        c.text(q, "q", qw, limit=200)
        c.text(q, "a", qw, limit=300)


def _check_oral(c: _Checker, items: list[dict], w: str, skills: set[str], seen: set[str]) -> None:
    """Questions for the oral exam (Foxy asks them aloud; the answer is checked against the key points)."""
    for i, q in enumerate(items):
        qw = f"{w}.oral[{i}]"
        c.only(q, {"id", "skill", "question", "key_points", "model_answer"}, qw)
        qid = q.get("id")
        if not isinstance(qid, str) or not TASK_ID_RE.fullmatch(qid) or qid in seen:
            c.bad(qw, f"oral id {qid!r} must be unique in the topic (a-z, 0-9 and -)")
        seen.add(str(qid))
        c.skill(q, qw, skills)
        c.text(q, "question", qw, limit=300)
        c.texts(q, "key_points", qw, 1, 6, 150)
        c.text(q, "model_answer", qw, limit=800)


def check_topic(c: _Checker, s: dict, w: str) -> None:
    c.only(s, {"id", "version", "format", "subject", "grade", "title", "intro", "source", "for", "skills", "learn",
               "study", "tasks", "challenge", "parent", "oral", "terms"}, w)
    if s.get("format", 1) not in (1, 2):
        c.bad(w, "\"format\" must be 1 or 2")
    skills: set[str] = set()
    for i, sk in enumerate(c.objects(s, "skills", w, 1, 12) if "skills" in s else []):
        kw = f"{w}.skills[{i}]"
        c.only(sk, {"id", "title"}, kw)
        c.text(sk, "title", kw, limit=80)
        sid = sk.get("id")
        if not isinstance(sid, str) or not TASK_ID_RE.fullmatch(sid) or sid in skills:
            c.bad(kw, f"skill id {sid!r} must be unique (a-z, 0-9 and -)")
        skills.add(str(sid))
    if "study" in s:
        _check_study(c, s["study"], f"{w}.study", skills)
    if "parent" in s:
        _check_parent(c, s["parent"], f"{w}.parent")
    for i, term in enumerate(c.objects(s, "terms", w, 1, 40) if "terms" in s else []):
        tw = f"{w}.terms[{i}]"
        c.only(term, {"term", "meaning"}, tw)
        c.text(term, "term", tw, limit=60)
        c.text(term, "meaning", tw, limit=200)
    # "for": the children (first names) the topic was made for; the parent's approval starts with them picked.
    if "for" in s:
        c.texts(s, "for", w, 1, 5, 40)
    v = s.get("version")
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        c.bad(w, "\"version\" must be a whole number from 1 (raise it after every change)")
    if s.get("subject") not in SUBJECTS:
        c.bad(w, f"\"subject\" must be one of {', '.join(SUBJECTS)}")
    g = s.get("grade")
    if not isinstance(g, int) or isinstance(g, bool) or g not in GRADES:
        c.bad(w, "\"grade\" must be 1–9 (razred) or 10–13 (1.–4. letnik)")
    c.text(s, "title", w, limit=80)
    c.text(s, "intro", w, limit=300)
    c.text(s, "source", w, optional=True, limit=300)

    learn = s.get("learn", [])
    if not isinstance(learn, list) or len(learn) > 8 or not all(isinstance(x, dict) for x in learn):
        c.bad(w, "\"learn\" must list 0–8 cards")
        learn = []
    for i, card in enumerate(learn):
        lw = f"{w}.learn[{i}]"
        c.only(card, {"title", "text", "example"}, lw)
        c.text(card, "title", lw, limit=60)
        c.text(card, "text", lw, limit=600)
        c.text(card, "example", lw, optional=True, limit=400)

    seen: set[str] = set()
    tasks = s.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 40 or not all(isinstance(t, dict) for t in tasks):
        c.bad(w, "\"tasks\" must list 1–40 tasks")
        tasks = []
    last_level = 1
    for i, t in enumerate(tasks):
        tid = t.get("id")
        tw = f"{w}.tasks[{i}]"
        if not isinstance(tid, str) or not TASK_ID_RE.fullmatch(tid):
            c.bad(tw, f"bad id {tid!r} (a-z, 0-9 and -)")
        elif tid in seen:
            c.bad(tw, f"duplicate id {tid!r}")
        else:
            seen.add(tid)
            tw = f"{w}.{tid}"
        _check_task(c, t, tw, skills)
        level = t.get("level")
        # Easy first: the levels never go back down (bonus tasks may come anywhere).
        if isinstance(level, int) and not t.get("extra"):
            if level < last_level:
                c.bad(tw, f"level {level} after level {last_level}: order the tasks from easy to harder")
            last_level = max(last_level, level)

    # The challenge level ("Liga prvakov"): harder tasks that open after the practice is finished once.
    if "challenge" in s:
        challenge = s["challenge"]
        if not isinstance(challenge, list) or not 1 <= len(challenge) <= 20 or not all(isinstance(t, dict) for t in challenge):
            c.bad(w, "\"challenge\" must list 1–20 tasks")
            challenge = []
        for i, t in enumerate(challenge):
            tid = t.get("id")
            tw = f"{w}.challenge[{i}]"
            if not isinstance(tid, str) or not TASK_ID_RE.fullmatch(tid):
                c.bad(tw, f"bad id {tid!r} (a-z, 0-9 and -)")
            elif tid in seen:
                c.bad(tw, f"duplicate id {tid!r} (ids must differ from the practice tasks too)")
            else:
                seen.add(tid)
                tw = f"{w}.{tid}"
            _check_task(c, t, tw, skills)
            if t.get("level") != 3:
                c.bad(tw, "challenge tasks are level 3")
            if len(t.get("hints") or []) > 1:
                c.bad(tw, "a challenge task has at most one hint")

    if "oral" in s:
        _check_oral(c, c.objects(s, "oral", w, 1, 20), w, skills, set())

    # Kid-facing Slovene addresses the child without gendered forms.
    kid_parts = {k: s[k] for k in ("intro", "learn", "study", "tasks", "challenge", "oral") if k in s}
    for text in _kid_texts(kid_parts):
        if m := _GENDERED_YOU.search(text):
            c.bad(w, f"gendered \"you\" ({m.group(0)!r}): use the imperative or present tense instead")


DEFAULT_SCALE = {"5": 90, "4": 76, "3": 63, "2": 50}  # % of points for each grade (a common Slovenian scale)


def check_mock(c: _Checker, m: dict, w: str, topics: dict[str, dict[str, Any]], scope_ok) -> None:
    """A mock test ("Poskusni test"): the teacher's format, timed, no hints, points per task. Every task
    belongs to one of the mock's topics (and may name a skill of that topic), so the result feeds mastery."""
    c.only(m, {"id", "version", "subject", "grade", "title", "intro", "source", "for", "minutes", "topics", "scale", "sections"}, w)
    v = m.get("version")
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        c.bad(w, "\"version\" must be a whole number from 1 (raise it after every change)")
    if m.get("subject") not in SUBJECTS:
        c.bad(w, f"\"subject\" must be one of {', '.join(SUBJECTS)}")
    if m.get("grade") not in GRADES:
        c.bad(w, "\"grade\" must be 1–13")
    c.text(m, "title", w, limit=80)
    c.text(m, "intro", w, limit=400)
    c.text(m, "source", w, optional=True, limit=300)
    if "for" in m:
        c.texts(m, "for", w, 1, 5, 40)
    minutes = m.get("minutes")
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 5 <= minutes <= 120:
        c.bad(w, "\"minutes\" must be 5–120")
    tids = m.get("topics")
    if not isinstance(tids, list) or not 1 <= len(tids) <= 6 or not all(isinstance(x, str) for x in tids):
        c.bad(w, "\"topics\" must list 1–6 topic ids")
        tids = []
    for tid in tids:
        if tid not in topics:
            c.bad(w, f"unknown topic {tid!r}")
        elif not scope_ok(tid):
            c.bad(w, f"topic {tid!r} belongs to another family")
    scale = m.get("scale", DEFAULT_SCALE)
    if (not isinstance(scale, dict) or set(scale) != {"2", "3", "4", "5"}
            or not all(isinstance(x, int) and 0 < x <= 100 for x in scale.values())
            or not scale["2"] < scale["3"] < scale["4"] < scale["5"]):
        c.bad(w, "\"scale\" must give % for grades \"2\" < \"3\" < \"4\" < \"5\"")
    seen: set[str] = set()
    sections = c.objects(m, "sections", w, 1, 8)
    total = 0
    for si, sec in enumerate(sections):
        sw = f"{w}.sections[{si}]"
        c.only(sec, {"title", "tasks"}, sw)
        c.text(sec, "title", sw, limit=80)
        for i, t in enumerate(c.objects(sec, "tasks", sw, 1, 20)):
            tid = t.get("id")
            tw = f"{sw}.tasks[{i}]"
            if not isinstance(tid, str) or not TASK_ID_RE.fullmatch(tid) or tid in seen:
                c.bad(tw, f"task id {tid!r} must be unique in the mock (a-z, 0-9 and -)")
            seen.add(str(tid))
            task = {k: v for k, v in t.items() if k not in ("points", "topic")}
            task.setdefault("level", 2)
            topic = topics.get(t.get("topic", ""))
            if t.get("topic") not in tids:
                c.bad(tw, "\"topic\" must be one of the mock's topics")
            _check_task(c, task, tw, {s["id"] for s in (topic or {}).get("skills", [])})
            if task.get("hints"):
                c.bad(tw, "a mock test has no hints")
            pts = t.get("points")
            if not isinstance(pts, (int, float)) or isinstance(pts, bool) or not 0.5 <= pts <= 20:
                c.bad(tw, "\"points\" must be 0.5–20")
            else:
                total += pts
    if sections and total <= 0:
        c.bad(w, "the mock has no points")
    for text in _kid_texts({"intro": m.get("intro"), "sections": sections}):
        if mt := _GENDERED_YOU.search(text):
            c.bad(w, f"gendered \"you\" ({mt.group(0)!r}): use the imperative or present tense instead")


def grade_for(pct: float, scale: dict[str, int] | None = None) -> int:
    """The grade a share of points (0–100) would get on the scale (1 below the lowest)."""
    s = scale or DEFAULT_SCALE
    for g in ("5", "4", "3", "2"):
        if pct >= s[g]:
            return int(g)
    return 1


def mock_tasks(m: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for sec in m["sections"] for t in sec["tasks"]]


def _read(path: Path, c: _Checker) -> dict[str, Any] | None:
    try:
        s = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        c.bad(path.name, f"not valid JSON: {exc}")
        return None
    if not isinstance(s, dict):
        c.bad(path.name, "must be a JSON object")
        return None
    if not ID_RE.fullmatch(path.stem):
        c.bad(path.name, "the file name must use a-z, 0-9 and - only")
    if s.get("id") != path.stem:
        c.bad(path.name, f"\"id\" must match the file name ({path.stem})")
    return s


def topic_folders(directory: Path = DATA_DIR) -> list[tuple[str, Path]]:
    """(scope, folder) for every topics folder: "global" first, then each family slug."""
    out = [("global", directory / "global" / "topics")]
    families = directory / "families"
    if families.is_dir():
        for fam in sorted(p for p in families.iterdir() if p.is_dir()):
            out.append((fam.name, fam / "topics"))
    return out


def load(directory: Path = DATA_DIR) -> Content:
    c = _Checker()
    topics: dict[str, dict[str, Any]] = {}
    scope: dict[str, str] = {}
    for slug, folder in topic_folders(directory):
        if slug != "global" and not SLUG_RE.fullmatch(slug):
            c.bad(f"families/{slug}", "a family folder is named after the family's slug (a-z, 0-9 and -)")
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            s = _read(path, c)
            if s is None:
                continue
            if path.stem in topics:
                c.bad(path.name, f"the id is used twice ({scope[path.stem]} and {slug})")
                continue
            check_topic(c, s, path.stem)
            topics[path.stem] = s
            scope[path.stem] = slug
    mocks: dict[str, dict[str, Any]] = {}
    for slug, folder in topic_folders(directory):
        mock_dir = folder.parent / "mocks"
        for path in sorted(mock_dir.glob("*.json")) if mock_dir.is_dir() else []:
            m = _read(path, c)
            if m is None:
                continue
            if path.stem in topics or path.stem in mocks:
                c.bad(path.name, "the id is used twice")
                continue
            check_mock(c, m, path.stem, topics, lambda tid, s=slug: scope.get(tid) in ("global", s))
            mocks[path.stem] = m
            scope[path.stem] = slug
    if c.problems:
        raise ContentError("Topics have problems:\n  " + "\n  ".join(c.problems))
    return Content(topics=topics, scope=scope, order=tuple(sorted(topics, reverse=True)), mocks=mocks,
                   mock_order=tuple(sorted(mocks, reverse=True)))


def summary(content: Content) -> list[str]:
    lines = []
    for tid in content.order:
        s = content.topics[tid]
        levels = [sum(1 for t in s["tasks"] if t["level"] == lv) for lv in LEVELS]
        st = s.get("study") or {}
        lines.append(f"  {tid:<40} {content.scope[tid]:<10} v{s['version']}  {s['subject']:<8} grade {s['grade']:<2} "
                     f"{len(s['tasks'])} tasks ({levels[0]}/{levels[1]}/{levels[2]}), challenge {len(s.get('challenge', []))}, "
                     f"cards {len(st.get('cards', []))}, skills {len(s.get('skills', []))}")
    return lines


if __name__ == "__main__":  # backend\.venv\Scripts\python.exe -m app.content.checker
    try:
        content = load()
    except ContentError as exc:
        print(exc)
        sys.exit(1)
    print(f"OK: {len(content.topics)} topics, {len(content.mocks)} mock tests.")
    print("\n".join(summary(content)))
    for mid in content.mock_order:
        m = content.mocks[mid]
        tasks = mock_tasks(m)
        print(f"  {mid:<40} {content.scope[mid]:<10} v{m['version']}  mock  {len(tasks)} tasks, "
              f"{sum(t['points'] for t in tasks):g} points, {m['minutes']} min")
