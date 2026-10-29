from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.content.checker import DATA_DIR, ContentError, goal_list, load, parse_answer

PRIMER = "2026-10-17-primer-ulomki"


def test_real_content_loads_with_scopes():
    c = load()
    assert c.scope[PRIMER] == "global"
    assert c.scope["2026-10-17-erik-english-people"] == "danijel"
    assert PRIMER in c.for_family("someone-else")
    assert "2026-10-17-erik-english-people" not in c.for_family("someone-else")
    assert "2026-10-17-erik-english-people" in c.for_family("danijel")


def test_parse_answer():
    assert parse_answer("2,5") == parse_answer(2.5) == parse_answer("5/2")
    assert parse_answer("1 3/4") == parse_answer("7/4")
    assert parse_answer("2.5") is None and parse_answer("1/0") is None and parse_answer(True) is None


def _copy(tmp_path: Path) -> Path:
    shutil.copytree(DATA_DIR, tmp_path / "data")
    return tmp_path / "data"


def _edit(data: Path, rel: str, change) -> None:
    p = data / rel
    s = json.loads(p.read_text(encoding="utf-8"))
    change(s)
    p.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def _problems(data: Path) -> str:
    with pytest.raises(ContentError) as exc:
        load(data)
    return str(exc.value)


def test_gendered_you_is_refused(tmp_path):
    data = _copy(tmp_path)
    _edit(data, f"global/topics/{PRIMER}.json", lambda s: s.update(intro="Si naredil vse naloge? Bravo!"))
    assert "gendered" in _problems(data)


def test_gender_neutral_text_passes(tmp_path):
    data = _copy(tmp_path)
    _edit(data, f"global/topics/{PRIMER}.json", lambda s: s.update(intro="Izračunaj in zapiši. Luka je igral 40 minut."))
    load(data)


def test_ids_are_unique_across_folders(tmp_path):
    data = _copy(tmp_path)
    (data / "families" / "other" / "topics").mkdir(parents=True)
    shutil.copy(data / "global" / "topics" / f"{PRIMER}.json", data / "families" / "other" / "topics")
    assert "used twice" in _problems(data)


def test_format_2_fields(tmp_path):
    data = _copy(tmp_path)

    def v2(s):
        s["format"] = 2
        s["skills"] = [{"id": "pomen", "title": "Kaj je ulomek"}, {"id": "del", "title": "Del od celote"}]
        s["tasks"][0]["skill"] = "pomen"
        s["tasks"][3]["traps"] = [{"answer": "4", "why": "To je imenovalec, ne rezultat."}]
        s["study"] = {"goals": [{"id": "pomen", "text": "Znam povedati, kaj je ulomek.", "skill": "pomen"}],
                      "sections": [{"title": "Ulomek", "text": "Števec in imenovalec.", "skill": "pomen"}],
                      "cards": [{"front": "števec", "back": "zgoraj", "skill": "pomen"}]}
        s["parent"] = {"school_method": "Ulomek kot del pice.", "car_questions": [{"q": "Koliko je 1/2 od 10?", "a": "5"}]}
        s["oral"] = [{"id": "o1", "skill": "pomen", "question": "Kaj pove imenovalec?",
                      "key_points": ["na koliko enakih delov"], "model_answer": "Na koliko enakih delov razdelimo celoto."}]
        s["terms"] = [{"term": "števec", "meaning": "število nad ulomkovo črto"}]

    _edit(data, f"global/topics/{PRIMER}.json", v2)
    t = load(data).topics[PRIMER]
    assert goal_list(t["study"]) == [{"id": "pomen", "text": "Znam povedati, kaj je ulomek.", "skill": "pomen"}]

    _edit(data, f"global/topics/{PRIMER}.json", lambda s: s["tasks"][1].update(skill="nope"))
    assert "unknown skill 'nope'" in _problems(data)


def test_video_lesson(tmp_path):
    data = _copy(tmp_path)
    video = {"title": "🎬 Ulomki", "scenes": [
        {"type": "intro", "emoji": "🍕", "title": "Ulomki", "foxy": "Živjo, {name}! Gremo na pico."},
        {"type": "rule", "title": "Števec in imenovalec", "steps": [{"sl": "Imenovalec pove, na koliko delov režemo."}, {"en": "one half"}]},
        {"type": "pairs", "title": "Besede", "say": [1], "pairs": [["polovica", "half"], ["četrtina", "quarter"]]},
        {"type": "quiz", "question": "1/2 od 10 je …", "options": ["2", "5"], "answer": 1, "explain": "10 : 2 = 5"},
        {"type": "recap", "title": "Konec", "points": ["Imenovalec je spodaj."]},
    ]}
    _edit(data, f"global/topics/{PRIMER}.json", lambda s: s.update(video=video))
    assert load(data).topics[PRIMER]["video"]["scenes"][3]["answer"] == 1

    def broken(s):
        s["video"]["scenes"][3]["answer"] = 5
        s["video"]["scenes"][1]["steps"] = [{}]
        s["video"]["scenes"][2]["say"] = [2]
        s["video"]["scenes"].append({"type": "song", "title": "?"})
        s["video"]["scenes"][0]["foxy"] = "Si pripravljen?"

    _edit(data, f"global/topics/{PRIMER}.json", broken)
    msg = _problems(data)
    for part in ("\"answer\" must be the number", "a step needs", "\"say\" lists the sides", "\"type\" must be one of", "gendered"):
        assert part in msg


def test_legacy_goals_get_ids():
    assert goal_list({"goals": ["A", "B"]}) == [{"id": "g0", "text": "A"}, {"id": "g1", "text": "B"}]
    assert goal_list(None) == []


def test_broken_topic_is_refused(tmp_path):
    data = _copy(tmp_path)
    _edit(data, f"global/topics/{PRIMER}.json", lambda s: s["tasks"][0].update(answer=99))
    _edit(data, f"global/topics/{PRIMER}.json", lambda s: s.update(version=0))
    msg = _problems(data)
    assert "\"answer\" must be the number of the right option" in msg and "\"version\"" in msg
