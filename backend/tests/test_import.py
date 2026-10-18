"""Moving Study data from PitchDriven: a synthetic PitchDriven database (the layout of its migrations 0001–0013)
is exported with the real exporter script, run the way it runs on the server, and imported into a scratch
family. Never real data, never the server."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import uuid
import zipfile
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.content import registry
from app.content.checker import load
from app.db import SessionLocal
from app.importers import pitchdriven as pd
from app.models import (Attachment, ContentAccess, DataImport, Learner, LlmCall, PracticeRun, TaskResult, TopicProgress,
                        TutorChat, TutorMessage)
from app.tutor import service as tutor

from .conftest import make_family

EXPORTER = Path(__file__).resolve().parents[2] / "scripts" / "export_pitchdriven_study.py"
GLOBAL = "2026-10-01-pd-test-fractions"  # offered to every family
OWN = "2026-10-02-pd-test-english"  # in the importing family's own folder
OTHER = "2026-10-03-pd-test-other"  # another family's private topic
MODELS = (Learner, ContentAccess, PracticeRun, TaskResult, TopicProgress, TutorChat, TutorMessage, Attachment, LlmCall,
          DataImport)


# --------------------------------------------------------------------------- #
# Scratch topics
# --------------------------------------------------------------------------- #
def _topic(tid: str, subject: str = "math") -> dict:
    return {
        "id": tid, "version": 2, "subject": subject, "grade": 6, "title": "Test topic", "intro": "Practise step by step.",
        "skills": [{"id": "add", "title": "Adding"}, {"id": "mul", "title": "Multiplying"}],
        "study": {"goals": ["I can add.", "I can multiply.", "I can check my work."],
                  "sections": [{"title": "Notes", "text": "Add the numbers, then check."}],
                  "cards": [{"front": "2 + 2", "back": "4"}, {"front": "3 x 3", "back": "9"}]},
        "tasks": [
            {"id": "t1", "level": 1, "kind": "number", "prompt": "2 + 3 = ?", "answer": 5, "solution": "2 + 3 = 5",
             "skill": "add"},
            {"id": "t2", "level": 2, "kind": "choice", "prompt": "3 x 3 = ?", "options": ["6", "9"], "answer": 1,
             "solution": "3 x 3 = 9", "skill": "mul"},
            {"id": "t3", "level": 2, "kind": "open", "prompt": "Explain how to add two numbers.",
             "solution": "Put both amounts together."},
        ],
        "challenge": [{"id": "c1", "level": 3, "kind": "text", "prompt": "Write 9 in words.", "answer": "nine",
                       "solution": "nine", "skill": "mul"}],
    }


@pytest.fixture()
def topics(tmp_path):
    """make(slug): scratch topics (one global, one of the family <slug>, one of another family) as the content."""
    def make(slug: str) -> None:
        root = tmp_path / "content"
        for rel, t in ((f"global/topics/{GLOBAL}.json", _topic(GLOBAL)),
                       (f"families/{slug}/topics/{OWN}.json", _topic(OWN, "english")),
                       (f"families/someone-else/topics/{OTHER}.json", _topic(OTHER))):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(json.dumps(t), encoding="utf-8")
        load(root)  # the scratch topics pass the checker
        registry.set_source(registry.FileContentSource(root))

    yield make
    registry.set_source(registry.FileContentSource())


# --------------------------------------------------------------------------- #
# A synthetic PitchDriven database and data folder
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num));
CREATE TABLE players (
    id INTEGER NOT NULL, name VARCHAR(80) NOT NULL, age INTEGER, role VARCHAR(20) NOT NULL, color VARCHAR(20) NOT NULL,
    avatar VARCHAR(16) NOT NULL, simple_mode BOOLEAN NOT NULL, sort_order INTEGER NOT NULL, archived BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL, PRIMARY KEY (id));
CREATE TABLE users (
    id INTEGER NOT NULL, username VARCHAR(80) NOT NULL, password_hash VARCHAR(300) NOT NULL, created_at DATETIME NOT NULL,
    password_changed_at DATETIME NOT NULL, role VARCHAR(20) DEFAULT 'admin' NOT NULL,
    player_id INTEGER REFERENCES players (id) ON DELETE SET NULL, language VARCHAR(5), PRIMARY KEY (id), UNIQUE (username));
CREATE TABLE auth_sessions (
    id INTEGER NOT NULL, user_id INTEGER NOT NULL, token_hash VARCHAR(64) NOT NULL, created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL, last_seen_at DATETIME NOT NULL, user_agent VARCHAR(300), PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, UNIQUE (token_hash));
CREATE TABLE study_profiles (
    player_id INTEGER NOT NULL, grade INTEGER, tutor_enabled BOOLEAN DEFAULT '1' NOT NULL,
    daily_limit INTEGER DEFAULT '30' NOT NULL, notes TEXT, updated_at DATETIME NOT NULL, PRIMARY KEY (player_id),
    FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE);
CREATE TABLE study_approvals (
    set_id VARCHAR(80) NOT NULL, version INTEGER NOT NULL, player_ids JSON NOT NULL, approved_at DATETIME NOT NULL,
    PRIMARY KEY (set_id));
CREATE TABLE study_attempts (
    id INTEGER NOT NULL, player_id INTEGER NOT NULL, set_id VARCHAR(80) NOT NULL, version INTEGER NOT NULL,
    results JSON NOT NULL, finished BOOLEAN DEFAULT '0' NOT NULL, local_date DATE NOT NULL, created_at DATETIME NOT NULL,
    challenge BOOLEAN DEFAULT '0' NOT NULL, PRIMARY KEY (id), FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE);
CREATE INDEX ix_study_attempts_player_id ON study_attempts (player_id);
CREATE TABLE study_chats (
    id INTEGER NOT NULL, player_id INTEGER NOT NULL, subject VARCHAR(20) DEFAULT 'other' NOT NULL,
    title VARCHAR(120) DEFAULT '' NOT NULL, parent_test BOOLEAN DEFAULT '0' NOT NULL, created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL, PRIMARY KEY (id), FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE);
CREATE INDEX ix_study_chats_player_id ON study_chats (player_id);
CREATE TABLE study_messages (
    id INTEGER NOT NULL, chat_id INTEGER NOT NULL, role VARCHAR(10) NOT NULL, text TEXT NOT NULL, image VARCHAR(64),
    model VARCHAR(60), input_tokens INTEGER DEFAULT '0' NOT NULL, output_tokens INTEGER DEFAULT '0' NOT NULL,
    cache_read_tokens INTEGER DEFAULT '0' NOT NULL, cache_write_tokens INTEGER DEFAULT '0' NOT NULL,
    cost_usd FLOAT DEFAULT '0' NOT NULL, local_date DATE NOT NULL, created_at DATETIME NOT NULL, PRIMARY KEY (id),
    FOREIGN KEY(chat_id) REFERENCES study_chats (id) ON DELETE CASCADE);
CREATE INDEX ix_study_messages_chat_id ON study_messages (chat_id);
CREATE TABLE study_progress (
    player_id INTEGER NOT NULL, set_id VARCHAR(80) NOT NULL, known JSON NOT NULL, goals JSON NOT NULL,
    updated_at DATETIME NOT NULL, PRIMARY KEY (player_id, set_id),
    FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE);
"""
T0 = "2026-09-01 08:00:00.000000"  # SQLAlchemy keeps UTC times naive in SQLite


def _r(first=False, tries=0, hints=0, shown=False, got_it=None, wrong=()) -> dict:
    return {"first": first, "tries": tries, "hints": hints, "shown": shown, "got_it": got_it, "wrong": list(wrong)}


def make_pitchdriven(root: Path, revision: str = "0013") -> dict:
    """Two kids (Erik, Alan), the parent's own player, and an archived player Study never used. Every call
    makes a different bundle (a random marker in a note), so no two tests share a bundle checksum."""
    data = root / "pd-data"
    db = data / "football7676.db"
    names = {k: f"{uuid.uuid4().hex}.{ext}" for k, ext in (("a", "jpg"), ("b", "png"), ("c", "webp"), ("gone", "jpg"))}
    photos = {"a": b"\xff\xd8\xff\xe0" + os.urandom(300), "b": b"\x89PNG\r\n\x1a\n" + os.urandom(300),
              "c": b"RIFF\x00\x00\x00\x00WEBP" + os.urandom(300)}
    for pid, key in ((1, "a"), (1, "b"), (2, "c")):
        (data / "study" / str(pid)).mkdir(parents=True, exist_ok=True)
        (data / "study" / str(pid) / names[key]).write_bytes(photos[key])
    (data / "study" / "1" / "notes.txt").write_text("not a photo")
    (data / "study" / "4").mkdir()
    (data / "study" / "4" / f"{uuid.uuid4().hex}.jpg").write_bytes(b"\xff\xd8\xff" + os.urandom(50))

    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    q = conn.execute
    q("INSERT INTO alembic_version VALUES (?)", (revision,))
    for row in ((1, "Erik", 12, "child", "#22c55e", "⚽", 0, 0, 0, T0), (2, "Alan", 10, "child", "#3b82f6", "🦁", 0, 1, 0, T0),
                (3, "Danijel", None, "parent", "#f59e0b", "🧔", 0, 2, 0, T0), (4, "Old Friend", 11, "child", "#999999", "⚽", 0, 3, 1, T0)):
        q("INSERT INTO players VALUES (?,?,?,?,?,?,?,?,?,?)", row)
    for row in ((1, "danijel", "scrypt$SECRET-HASH-ADMIN", T0, T0, "admin", None, None),
                (2, "erik", "scrypt$SECRET-HASH-ERIK", T0, T0, "player", 1, "en"),
                (3, "alan", "scrypt$SECRET-HASH-ALAN", T0, T0, "player", 2, None)):
        q("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", row)
    q("INSERT INTO auth_sessions VALUES (1, 2, 'SECRET-TOKEN-HASH', ?, ?, ?, 'Firefox')", (T0, T0, T0))
    q("INSERT INTO study_profiles VALUES (1, 7, 1, 20, ?, ?)", (f"Likes football examples. {uuid.uuid4().hex}", T0))
    q("INSERT INTO study_profiles VALUES (2, 5, 0, 10, NULL, ?)", (T0,))
    for set_id, version, pids in ((GLOBAL, 2, [1, 2, 3]), (OWN, 1, [1]), (OTHER, 1, [1])):
        q("INSERT INTO study_approvals VALUES (?,?,?,?)", (set_id, version, json.dumps(pids), "2026-10-01 09:00:00.000000"))
    attempts = (
        (1, 1, GLOBAL, 2, {"t1": _r(True, 1), "t2": _r(tries=2, hints=1, wrong=["6"]), "t3": _r(shown=True, got_it=True),
                           "gone": _r(True, 1)}, 1, "2026-10-10", "2026-10-10 15:00:00.000000", 0),
        (2, 1, GLOBAL, 2, {"c1": _r(True, 1)}, 1, "2026-10-11", "2026-10-11 16:00:00.000000", 1),
        (3, 2, OWN, 2, {"t1": _r(tries=3, hints=2, shown=True, wrong=["4", "6"])}, 0, "2026-10-12", "2026-10-12 17:00:00.000000", 0),
        (4, 3, GLOBAL, 2, {"t1": _r(True, 1)}, 1, "2026-10-12", "2026-10-12 18:00:00.000000", 0),
    )
    for a in attempts:
        q("INSERT INTO study_attempts VALUES (?,?,?,?,?,?,?,?,?)", (*a[:4], json.dumps(a[4]), *a[5:]))
    q("INSERT INTO study_progress VALUES (1, ?, '[\"4\"]', '[0, 2]', ?)", (GLOBAL, T0))
    q("INSERT INTO study_progress VALUES (2, ?, '[]', '[1, 7]', ?)", (OWN, T0))
    t3 = "2026-10-13 14:00:00.000000"
    for row in ((1, 1, "math", "Kako seštejem ulomke?", 0), (2, 1, "math", "Parent trying Foxy", 1), (3, 2, "chemistry", "📷", 0)):
        q("INSERT INTO study_chats VALUES (?,?,?,?,?,?,?)", (*row, t3, t3))
    messages = (
        (1, 1, "user", "Kako seštejem ulomke?", names["a"], None, 0, 0, 0, 0, 0.0),
        (2, 1, "assistant", "Najprej poišči skupni imenovalec.", None, "claude-opus-5-5", 1500, 200, 1000, 300, 0.0123),
        (3, 1, "user", "Hvala!", None, None, 0, 0, 0, 0, 0.0),
        (4, 1, "assistant", "Z veseljem!", None, "claude-opus-5-5", 1700, 50, 1200, 0, 0.0051),
        (5, 2, "user", "Test", names["b"], None, 0, 0, 0, 0, 0.0),
        (6, 2, "assistant", "Test reply", None, "claude-opus-5-5", 900, 40, 0, 900, 0.009),
        (7, 3, "user", "", names["gone"], None, 0, 0, 0, 0, 0.0),
        (8, 3, "assistant", "Na sliki vidim nalogo.", None, "claude-sonnet-5-5", 1200, 80, 0, 0, 0.003),
    )
    for m in messages:
        q("INSERT INTO study_messages VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (*m, "2026-10-13", t3))
    conn.commit()
    conn.close()
    return {"db": db, "data": data, "names": names, "photos": photos}


def export(pdb: dict, out: Path) -> subprocess.CompletedProcess:
    """As on the server: the script fed on stdin, standard library only (-S: no site-packages)."""
    with open(EXPORTER, "rb") as script:
        return subprocess.run([sys.executable, "-I", "-S", "-", "--db", str(pdb["db"]), "--data", str(pdb["data"]),
                               "--out", str(out)], stdin=script, capture_output=True, text=True, timeout=120)


def make_bundle(tmp_path: Path) -> tuple[dict, Path]:
    pdb = make_pitchdriven(tmp_path)
    out = tmp_path / "out" / "study-export.zip"
    r = export(pdb, out)
    assert r.returncode == 0, r.stderr
    return pdb, out


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in MODELS}


def _family_files(family_id: int) -> list[Path]:
    folder = settings.files_dir / str(family_id)
    return [p for p in folder.rglob("*") if p.is_file()] if folder.exists() else []


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def test_export_has_study_data_photos_and_no_secrets(tmp_path):
    pdb = make_pitchdriven(tmp_path)
    before = hashlib.sha256(pdb["db"].read_bytes()).hexdigest()
    out = tmp_path / "out" / "study-export.zip"
    r = export(pdb, out)
    assert r.returncode == 0, r.stderr
    assert "study_messages" in r.stdout and "1 photo(s) named in messages are missing" in r.stdout
    assert hashlib.sha256(pdb["db"].read_bytes()).hexdigest() == before  # read from a snapshot only

    with zipfile.ZipFile(out) as zf:
        m = json.loads(zf.read("manifest.json"))
        assert m["schema_revision"] == "0013" and m["created_at"].endswith("Z")
        assert m["counts"] == {"study_profiles": 2, "study_approvals": 3, "study_attempts": 4, "study_progress": 2,
                               "study_chats": 3, "study_messages": 8, "players": 3, "users": 3, "photos": 3}
        # The photos of the exported players only (not the archived player's, not the stray text file).
        names, photos = pdb["names"], pdb["photos"]
        assert set(m["photos"]) == {f"photos/1/{names['a']}", f"photos/1/{names['b']}", f"photos/2/{names['c']}"}
        assert m["photos"][f"photos/1/{names['a']}"]["sha256"] == hashlib.sha256(photos["a"]).hexdigest()
        assert zf.read(f"photos/2/{names['c']}") == photos["c"]
        assert m["missing_photos"] == [{"message_id": 7, "player_id": 2, "name": names["gone"]}]

        players = json.loads(zf.read("tables/players.json"))
        assert sorted(p["name"] for p in players) == ["Alan", "Danijel", "Erik"]
        users = json.loads(zf.read("tables/users.json"))
        assert all(set(u) == {"username", "role", "player_id", "language"} for u in users)
        attempts = json.loads(zf.read("tables/study_attempts.json"))
        assert attempts[1]["challenge"] is True and attempts[0]["results"]["t2"]["wrong"] == ["6"]
        # No password hash, no session, anywhere in the bundle.
        assert not any(n.startswith("tables/auth") for n in zf.namelist())
        for name in zf.namelist():
            data = zf.read(name)
            assert b"SECRET" not in data and b"password" not in data, name


def test_export_refuses_an_old_or_changed_schema(tmp_path):
    old = make_pitchdriven(tmp_path / "old", revision="0012")
    r = export(old, tmp_path / "old.zip")
    assert r.returncode == 1 and "0013" in r.stderr and not (tmp_path / "old.zip").exists()

    changed = make_pitchdriven(tmp_path / "changed", revision="0014")
    conn = sqlite3.connect(changed["db"])
    conn.execute("ALTER TABLE study_progress RENAME COLUMN goals TO goal_ids")
    conn.commit()
    conn.close()
    r = export(changed, tmp_path / "changed.zip")
    assert r.returncode == 1 and "study_progress" in r.stderr and not (tmp_path / "changed.zip").exists()

    later = make_pitchdriven(tmp_path / "later", revision="0014")  # a later revision with the same Study tables
    assert export(later, tmp_path / "later.zip").returncode == 0


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #
def test_import_round_trip(client, tmp_path, topics, capsys):
    topics("pd-imp")
    fam = make_family("pd-imp", [])
    pdb, bundle = make_bundle(tmp_path)
    args = [str(bundle), "--family", "pd-imp", "--learners", "Erik,Alan"]

    # A dry run checks and counts everything and writes nothing.
    before = _counts()
    assert pd.main(args + ["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN: nothing was written." in out and "Every bundle row is accounted for." in out
    assert "3 practice_runs" in out and "1 tasks no longer in their topic" in out and "1 parent test chats" in out
    assert _counts() == before and _family_files(fam.id) == []
    with SessionLocal() as db:
        rep = pd.import_bundle(db, bundle, "pd-imp", ["Erik", "Alan"], include_parent_tests=True, dry_run=True)
    assert rep.plan.written["tutor_chats"] == 3 and rep.plan.written["attachments"] == 2 and rep.balanced
    assert _counts() == before

    # The real import.
    assert pd.main(args) == 0
    out = capsys.readouterr().out
    assert "Imported (import #" in out and "Every bundle row is accounted for." in out
    assert "Photo missing in PitchDriven already: message 7" in out

    with SessionLocal() as db:
        learners = {lr.name: lr for lr in db.scalars(select(Learner).where(Learner.family_id == fam.id))}
        assert set(learners) == {"Erik", "Alan"}
        erik, alan = learners["Erik"], learners["Alan"]
        assert (erik.avatar, erik.color, erik.grade, erik.language, erik.tutor_enabled, erik.tutor_daily_limit) == \
               ("⚽", "#22c55e", 7, "en", True, 20)
        assert erik.tutor_notes.startswith("Likes football examples.")
        assert (alan.avatar, alan.grade, alan.language, alan.tutor_enabled, alan.tutor_daily_limit, alan.tutor_notes) == \
               ("🦁", 5, "sl", False, 10, None)

        # Approvals for the named kids, at the approved version (the own topic's file is newer: v2).
        access = {(a.content_id, a.learner_id, a.version, a.approved_by)
                  for a in db.scalars(select(ContentAccess).where(ContentAccess.family_id == fam.id))}
        assert access == {(GLOBAL, erik.id, 2, None), (GLOBAL, alan.id, 2, None), (OWN, erik.id, 1, None)}

        runs = list(db.scalars(select(PracticeRun).where(PracticeRun.family_id == fam.id).order_by(PracticeRun.started_at)))
        assert [(r.learner_id, r.mode, r.content_id, r.finished) for r in runs] == [
            (erik.id, "practice", GLOBAL, True), (erik.id, "challenge", GLOBAL, True), (alan.id, "practice", OWN, False)]
        practice, challenge, alans = runs
        assert practice.local_date == date(2026, 10, 10) and practice.version == 2 and practice.finished_at is not None
        assert alans.finished_at is None and practice.meta == {"imported_from": "pitchdriven", "attempt_id": 1}
        tr = {r.task_id: r for r in practice.results}
        assert set(tr) == {"t1", "t2", "t3"}  # "gone" is no longer in the topic
        t2 = tr["t2"]
        assert (t2.topic_id, t2.level, t2.kind, t2.skill_id, t2.first, t2.tries, t2.hints, t2.shown, t2.got_it, t2.wrong) == \
               (GLOBAL, 2, "choice", "mul", False, 2, 1, False, None, ["6"])
        assert (tr["t3"].kind, tr["t3"].skill_id, tr["t3"].got_it, tr["t3"].shown) == ("open", None, True, True)
        assert tr["t1"].local_date == date(2026, 10, 10) and tr["t1"].learner_id == erik.id
        [c1] = challenge.results
        assert (c1.task_id, c1.level, c1.kind, c1.skill_id, c1.first) == ("c1", 3, "text", "mul", True)
        [a1] = alans.results
        assert (a1.topic_id, a1.tries, a1.hints, a1.shown, a1.wrong) == (OWN, 3, 2, True, ["4", "6"])

        progress = {(p.learner_id, p.topic_id): p for p in db.scalars(select(TopicProgress).where(TopicProgress.family_id == fam.id))}
        assert (progress[(erik.id, GLOBAL)].goals, progress[(erik.id, GLOBAL)].known) == (["g0", "g2"], ["4"])
        assert progress[(alan.id, OWN)].goals == ["g1"]  # index 7 is not in the topic

        # Chats: the parent's test chat stays behind.
        chats = list(db.scalars(select(TutorChat).where(TutorChat.family_id == fam.id).order_by(TutorChat.id)))
        assert [(c.learner_id, c.subject, c.title, c.parent_test) for c in chats] == [
            (erik.id, "math", "Kako seštejem ulomke?", False), (alan.id, "other", "📷", False)]
        msgs = chats[0].messages
        assert [m.role for m in msgs] == ["user", "assistant", "user", "assistant"]
        assert msgs[0].text == "Kako seštejem ulomke?" and msgs[0].llm_call_id is None
        call = db.get(LlmCall, msgs[1].llm_call_id)
        assert (call.job, call.model, call.input_tokens, call.output_tokens, call.cache_read_tokens, call.cache_write_tokens,
                call.cost_usd, call.outcome, call.learner_id) == \
               ("tutor_chat", "claude-opus-5-5", 1500, 200, 1000, 300, 0.0123, "imported", erik.id)
        assert db.scalar(select(func.count(LlmCall.id)).where(LlmCall.family_id == fam.id)) == 3
        assert tutor.month_usage(db, fam.id, date(2026, 10, 20))["month_calls"] == 0  # imported costs aren't this month's spend
        assert chats[1].messages[0].attachments == []  # its photo was already missing in PitchDriven

        # The photo: copied, checksum checked, and served to the family.
        [att] = msgs[0].attachments
        f = tutor.files_dir(fam.id, erik.id) / att.file_name
        assert f.read_bytes() == pdb["photos"]["a"]
        assert att.sha256 == hashlib.sha256(pdb["photos"]["a"]).hexdigest() and att.media_type == "image/jpeg"
        assert att.bytes == len(pdb["photos"]["a"]) and att.learner_id == erik.id
        assert len(_family_files(fam.id)) == 1

        imp = db.scalars(select(DataImport).where(DataImport.family_id == fam.id)).one()
        assert imp.source == "pitchdriven" and imp.bundle_sha256 == hashlib.sha256(bundle.read_bytes()).hexdigest()
        assert imp.counts["written"]["practice_runs"] == 3 and imp.counts["learners"] == {"Erik": erik.id, "Alan": alan.id}
        assert imp.counts["skipped"]["study_chats"] == {"parent_test": 1}
        erik_id = erik.id

    assert fam.admin.get(f"/api/learners/{erik_id}/files/{att.file_name}").content == pdb["photos"]["a"]
    assert fam.admin.get(f"/api/learners/{erik_id}/topics/{GLOBAL}").status_code == 200
    assert fam.admin.get(f"/api/learners/{erik_id}/topics/{OWN}").status_code == 404  # v1 approved, v2 waits for a check

    # The same bundle can't be imported twice.
    counts = _counts()
    assert pd.main(args) == 1
    assert "already imported" in capsys.readouterr().err
    assert _counts() == counts


def test_a_failed_import_writes_nothing(client, tmp_path, topics):
    topics("pd-fail")
    fam = make_family("pd-fail", [])
    _pdb, bundle = make_bundle(tmp_path)
    before = _counts()
    with SessionLocal() as db:
        def broken_commit():
            raise RuntimeError("disk full")

        db.commit = broken_commit  # fails after every row was added and the photo was copied
        with pytest.raises(RuntimeError):
            pd.import_bundle(db, bundle, "pd-fail", ["Erik", "Alan"])
    assert _counts() == before and _family_files(fam.id) == []

    # Nothing was recorded either, so the bundle can still be imported.
    with SessionLocal() as db:
        rep = pd.import_bundle(db, bundle, "pd-fail", ["Erik", "Alan"])
    assert rep.import_id is not None and len(_family_files(fam.id)) == 1


def test_import_refusals(client, tmp_path, topics):
    topics("pd-refuse")
    make_family("pd-refuse", [])
    make_family("pd-clash", ["Erik"])
    _pdb, bundle = make_bundle(tmp_path)
    before = _counts()

    def refused(*, path=bundle, family="pd-refuse", learners=("Erik", "Alan")) -> str:
        with SessionLocal() as db, pytest.raises(pd.ImportRefused) as exc:
            pd.import_bundle(db, path, family, list(learners))
        return str(exc.value)

    assert "No player called 'Eva'" in refused(learners=("Erik", "Eva"))
    assert "No family 'nobody'" in refused(family="nobody")
    assert "already has a learner called Erik" in refused(family="pd-clash")
    assert "named twice" in refused(learners=("Erik", "erik"))

    damaged = tmp_path / "damaged.zip"
    with zipfile.ZipFile(bundle) as zin, zipfile.ZipFile(damaged, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename.startswith("photos/"):
                data = data[:-1] + bytes([data[-1] ^ 1])
            zout.writestr(info, data)
    assert "doesn't match its checksum" in refused(path=damaged)
    assert _counts() == before
