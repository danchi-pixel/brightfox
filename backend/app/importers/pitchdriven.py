"""Move Study data exported from PitchDriven into a BrightFox family (a one-off, for the move).

    python -m app.importers.pitchdriven <bundle.zip> --family <slug> --learners Erik,Alan [--include-parent-tests] [--dry-run]

The bundle comes from ``scripts/export_pitchdriven_study.py`` (run inside the PitchDriven container). The
import:

- checks the bundle: every table file and photo against the manifest's sha256, and the row counts;
- creates one new learner in the (existing) family for each named PitchDriven player, matched by name, with
  the player's avatar and color, the Study profile's grade and Foxy settings, and the kid account's language;
- turns approvals into ``content_access`` (approved_by empty), runs into ``practice_runs`` with one
  ``task_results`` row per task (level, kind and skill from the topic file; tasks no longer in the topic are
  skipped and counted), study progress into ``topic_progress`` (goal indexes become goal ids), and chats into
  ``tutor_chats``/``tutor_messages`` with an ``llm_calls`` row (outcome "imported") per Foxy answer and an
  ``attachments`` row per photo (the file copied to data/files/<family>/<learner>/ and its sha256 checked);
- skips the parent's own Foxy test chats unless ``--include-parent-tests``;
- records the bundle's sha256 in ``imports``, so the same bundle can't be imported twice.

Everything is written in one transaction: on any error nothing is written and the copied photos are
removed. ``--dry-run`` checks everything and prints what it would write, and writes nothing. No accounts or
passwords are imported: the parent sets the kids' passwords afterwards with ``python -m app.manage``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import uuid
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import IO, Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..content import registry
from ..content.checker import Content, ContentError, goal_list
from ..models import (Attachment, ContentAccess, DataImport, Family, Learner, LlmCall, PracticeRun, TaskResult,
                      TopicProgress, TutorChat, TutorMessage)
from ..tutor import service as tutor
from ..tutor.prompts import SUBJECTS

SOURCE = "pitchdriven"
FORMAT = 1
TABLES = ("study_profiles", "study_approvals", "study_attempts", "study_progress", "study_chats", "study_messages",
          "players", "users")
LANGUAGES = ("sl", "en")
EXTENSIONS = {"jpg": "jpg", "jpeg": "jpg", "png": "png", "webp": "webp"}

# How each kind of bundle row ends up here (the summary checks that every row is accounted for).
LEDGER = (
    ("players", "learners"),
    ("kid approvals", "content_access"),
    ("study_attempts", "practice_runs"),
    ("task results", "task_results"),
    ("study_progress", "topic_progress"),
    ("study_chats", "tutor_chats"),
    ("study_messages", "tutor_messages"),
    ("photos", "attachments"),
)
REASONS = {
    "not_named": "players not named",
    "unknown_topic": "topics this family can't see",
    "task_gone": "tasks no longer in their topic",
    "parent_test": "parent test chats",
    "no_chat": "no chat",
    "unused": "not used by an imported message",
}


class ImportRefused(Exception):
    """The bundle can't be imported (the message says why). Nothing was written."""


# --------------------------------------------------------------------------- #
# The bundle
# --------------------------------------------------------------------------- #
@dataclass
class Bundle:
    sha256: str
    manifest: dict[str, Any]
    tables: dict[str, list[dict[str, Any]]]
    zf: zipfile.ZipFile  # open while the import runs; photos are copied straight from it


def _stream_sha(f: IO[bytes]) -> tuple[str, int]:
    h, n = hashlib.sha256(), 0
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
        n += len(chunk)
    return h.hexdigest(), n


def _member(zf: zipfile.ZipFile, name: str) -> bytes:
    try:
        return zf.read(name)
    except KeyError:
        raise ImportRefused(f"The bundle lacks {name}.") from None


@contextmanager
def open_bundle(path: Path) -> Iterator[Bundle]:
    """The bundle with every checksum and count verified (photos are checked without loading them all)."""
    try:
        with open(path, "rb") as f:
            sha, _ = _stream_sha(f)
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ImportRefused(f"Can't open {path} as a zip: {exc}") from None
    with zf:
        try:
            manifest = json.loads(_member(zf, "manifest.json"))
        except ValueError:
            raise ImportRefused("manifest.json isn't valid JSON.") from None
        if manifest.get("source") != SOURCE or manifest.get("format") != FORMAT:
            raise ImportRefused("This isn't a bundle from export_pitchdriven_study.py (format 1).")
        counts = manifest.get("counts", {})
        tables: dict[str, list[dict[str, Any]]] = {}
        for table in TABLES:
            entry = manifest.get("tables", {}).get(table)
            if not entry:
                raise ImportRefused(f"The bundle has no {table} table.")
            data = _member(zf, entry["file"])
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ImportRefused(f"{entry['file']} doesn't match its checksum: the bundle is damaged.")
            rows = json.loads(data)
            if len(rows) != counts.get(table):
                raise ImportRefused(f"{table} has {len(rows)} rows, the manifest says {counts.get(table)}.")
            tables[table] = rows
        photos = manifest.get("photos", {})
        for name, entry in photos.items():
            try:
                with zf.open(name) as f:
                    got = _stream_sha(f)
            except KeyError:
                raise ImportRefused(f"The bundle lacks {name}.") from None
            if got != (entry["sha256"], entry["bytes"]):
                raise ImportRefused(f"{name} doesn't match its checksum: the bundle is damaged.")
        if len(photos) != counts.get("photos"):
            raise ImportRefused(f"The bundle has {len(photos)} photos, the manifest says {counts.get('photos')}.")
        yield Bundle(sha256=sha, manifest=manifest, tables=tables, zf=zf)


# --------------------------------------------------------------------------- #
# Planning: everything is checked and mapped before anything is written
# --------------------------------------------------------------------------- #
@dataclass
class Plan:
    names: dict[int, str]  # PitchDriven player id -> learner name
    learners: dict[int, dict[str, Any]] = field(default_factory=dict)  # player id -> Learner fields
    access: list[dict[str, Any]] = field(default_factory=list)
    runs: list[tuple[dict[str, Any], list[dict[str, Any]]]] = field(default_factory=list)
    progress: list[dict[str, Any]] = field(default_factory=list)
    chats: list[tuple[dict[str, Any], list[dict[str, Any]]]] = field(default_factory=list)
    source: Counter = field(default_factory=Counter)  # rows in the bundle, by LEDGER name
    written: Counter = field(default_factory=Counter)  # rows to write, by table
    skipped: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))  # LEDGER name -> reason -> n
    notes: list[str] = field(default_factory=list)


def _norm(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def _dt(value: Any) -> datetime:
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)  # SQLite keeps PitchDriven's UTC times naive


def _day(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _match_players(players: list[dict[str, Any]], names: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for name in names:
        hits = [p for p in players if _norm(p["name"]) == _norm(name)]
        if not hits:
            known = ", ".join(sorted(p["name"] for p in players)) or "none"
            raise ImportRefused(f"No player called {name!r} in the bundle (players: {known}).")
        if len(hits) > 1:
            raise ImportRefused(f"{len(hits)} players are called {name!r} (ids {', '.join(str(p['id']) for p in hits)}).")
        out[hits[0]["id"]] = " ".join(hits[0]["name"].split())[:40]
    return out


def build_plan(bundle: Bundle, names: list[str], content: Content, slug: str, include_parent_tests: bool,
               first_sort: int) -> Plan:
    t = bundle.tables
    plan = Plan(names=_match_players(t["players"], names))
    mapped = plan.names
    visible = set(content.for_family(slug))

    def topic(set_id: str) -> dict[str, Any] | None:
        return content.topics[set_id] if set_id in visible else None

    # Learners: the player, its Study profile and the kid account's language.
    plan.source["players"] = len(t["players"])
    plan.skipped["players"]["not_named"] = len(t["players"]) - len(mapped)
    profiles = {p["player_id"]: p for p in t["study_profiles"]}
    players = {p["id"]: p for p in t["players"]}
    for i, (pid, name) in enumerate(mapped.items()):
        p, prof = players[pid], profiles.get(pid, {})
        lang = next((u["language"] for u in t["users"] if u["role"] == "player" and u["player_id"] == pid
                     and u["language"]), None) or "sl"
        if lang not in LANGUAGES:
            plan.notes.append(f"{name}'s PitchDriven language {lang!r} isn't offered here: using 'sl'.")
            lang = "sl"
        grade = prof.get("grade")
        plan.learners[pid] = {
            "name": name, "avatar": p.get("avatar") or "🦊", "color": p.get("color") or "#e8590c",
            "grade": grade if isinstance(grade, int) and 1 <= grade <= 13 else None, "language": lang,
            "tutor_enabled": bool(prof.get("tutor_enabled", True)),
            "tutor_daily_limit": int(prof["daily_limit"]) if prof.get("daily_limit") is not None else 30,
            "tutor_notes": prof.get("notes") or None, "sort_order": first_sort + i,
        }
    plan.written["learners"] = len(plan.learners)

    # Approvals: one content_access row per named kid, at the approved version.
    for a in t["study_approvals"]:
        for raw in a["player_ids"] or []:
            plan.source["kid approvals"] += 1
            pid = int(raw)
            if pid not in mapped:
                plan.skipped["kid approvals"]["not_named"] += 1
            elif topic(a["set_id"]) is None:
                plan.skipped["kid approvals"]["unknown_topic"] += 1
            else:
                plan.access.append({"pid": pid, "kind": "topic", "content_id": a["set_id"], "version": int(a["version"]),
                                    "approved_by": None, "approved_at": _dt(a["approved_at"])})
    plan.written["content_access"] = len(plan.access)

    # Runs: one task_results row per task, described by the topic file.
    plan.source["study_attempts"] = len(t["study_attempts"])
    unknown_runs = 0
    for at in t["study_attempts"]:
        results = at["results"] or {}
        plan.source["task results"] += len(results)
        pid = at["player_id"]
        if pid not in mapped:
            plan.skipped["study_attempts"]["not_named"] += 1
            plan.skipped["task results"]["not_named"] += len(results)
            continue
        tp = topic(at["set_id"])
        unknown_runs += tp is None
        tasks = {x["id"]: x for x in (tp["tasks"] + tp.get("challenge", []))} if tp else {}
        day, started = _day(at["local_date"]), _dt(at["created_at"])
        run = {"pid": pid, "mode": "challenge" if at.get("challenge") else "practice", "content_id": at["set_id"],
               "version": int(at["version"]), "finished": bool(at["finished"]), "local_date": day,
               "started_at": started, "finished_at": started if at["finished"] else None,
               "meta": {"imported_from": SOURCE, "attempt_id": at["id"]}}
        rows = []
        for task_id, r in results.items():
            task = tasks.get(task_id)
            if task is None:
                plan.skipped["task results"]["task_gone"] += 1
                continue
            rows.append({"topic_id": at["set_id"], "task_id": task_id, "skill_id": task.get("skill"),
                         "level": task["level"], "kind": task["kind"], "first": bool(r.get("first")),
                         "tries": int(r.get("tries") or 0), "hints": int(r.get("hints") or 0),
                         "shown": bool(r.get("shown")), "got_it": None if r.get("got_it") is None else bool(r["got_it"]),
                         "wrong": [str(w) for w in r.get("wrong") or []], "local_date": day})
        plan.runs.append((run, rows))
        plan.written["task_results"] += len(rows)
    plan.written["practice_runs"] = len(plan.runs)
    if unknown_runs:
        plan.notes.append(f"{unknown_runs} run(s) are for topics this family can't see: imported without their tasks.")

    # Study progress: goal indexes become goal ids ("g<i>" in format-1 topics).
    plan.source["study_progress"] = len(t["study_progress"])
    goals_gone = 0
    for pr in t["study_progress"]:
        pid = pr["player_id"]
        if pid not in mapped:
            plan.skipped["study_progress"]["not_named"] += 1
            continue
        tp = topic(pr["set_id"])
        idx = sorted({int(i) for i in pr["goals"] or []})
        if tp is not None:
            listed = goal_list(tp.get("study"))
            goals = [g["id"] for i, g in enumerate(listed) if i in idx]
            goals_gone += len(idx) - len(goals)
        else:
            goals = [f"g{i}" for i in idx]
        plan.progress.append({"pid": pid, "topic_id": pr["set_id"], "known": list(dict.fromkeys(pr["known"] or [])),
                              "goals": goals, "updated_at": _dt(pr["updated_at"])})
    plan.written["topic_progress"] = len(plan.progress)
    if goals_gone:
        plan.notes.append(f"{goals_gone} ticked goal(s) are no longer in their topic: left out.")

    # Chats, their messages, a ledger row per Foxy answer and the photos.
    plan.source["study_chats"] = len(t["study_chats"])
    plan.source["study_messages"] = len(t["study_messages"])
    plan.source["photos"] = len(bundle.manifest["photos"])
    by_chat: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for m in sorted(t["study_messages"], key=lambda m: m["id"]):
        by_chat[m["chat_id"]].append(m)
    chat_ids = {c["id"] for c in t["study_chats"]}
    plan.skipped["study_messages"]["no_chat"] = sum(len(ms) for cid, ms in by_chat.items() if cid not in chat_ids)
    used: set[str] = set()
    missing = 0
    for ch in t["study_chats"]:
        pid, ms = ch["player_id"], by_chat.get(ch["id"], [])
        reason = "not_named" if pid not in mapped else "parent_test" if ch["parent_test"] and not include_parent_tests else None
        if reason:
            plan.skipped["study_chats"][reason] += 1
            plan.skipped["study_messages"][reason] += len(ms)
            continue
        title = ch["title"] or ""
        chat = {"pid": pid, "subject": ch["subject"] if ch["subject"] in SUBJECTS else "other", "topic_id": None,
                "task_id": None, "title": title if len(title) <= 80 else title[:79] + "…",
                "parent_test": bool(ch["parent_test"]), "created_at": _dt(ch["created_at"]),
                "updated_at": _dt(ch["updated_at"])}
        messages = []
        for m in ms:
            day, created = _day(m["local_date"]), _dt(m["created_at"])
            msg: dict[str, Any] = {"fields": {"role": m["role"], "text": m["text"] or "", "local_date": day,
                                              "created_at": created}, "llm": None, "photo": None}
            if m["role"] == "assistant":
                msg["llm"] = {"job": "tutor_chat", "provider": "anthropic", "model": (m["model"] or "unknown")[:60],
                              "input_tokens": int(m["input_tokens"] or 0), "output_tokens": int(m["output_tokens"] or 0),
                              "cache_read_tokens": int(m["cache_read_tokens"] or 0),
                              "cache_write_tokens": int(m["cache_write_tokens"] or 0),
                              "cost_usd": float(m["cost_usd"] or 0.0), "outcome": "imported", "local_date": day,
                              "created_at": created}
                plan.written["llm_calls"] += 1
            if m["image"]:
                name = f"photos/{pid}/{m['image']}"
                entry = bundle.manifest["photos"].get(name)
                ext = EXTENSIONS.get(str(m["image"]).rsplit(".", 1)[-1].lower())
                if entry is None or ext is None:
                    missing += 1
                else:
                    msg["photo"] = {"zip": name, "ext": ext, **entry}
                    used.add(name)
                    plan.written["attachments"] += 1
            messages.append(msg)
        plan.chats.append((chat, messages))
        plan.written["tutor_messages"] += len(messages)
    plan.written["tutor_chats"] = len(plan.chats)
    plan.skipped["photos"]["unused"] = plan.source["photos"] - len(used)
    if missing:
        plan.notes.append(f"{missing} message(s) name a photo that isn't in the bundle: imported without it.")
    return plan


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def _fields(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != "pid"}


def _copy_photo(bundle: Bundle, family_id: int, learner_id: int, photo: dict[str, Any], written: list[Path]) -> Attachment:
    folder = tutor.files_dir(family_id, learner_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{photo['ext']}"
    target = folder / name
    with bundle.zf.open(photo["zip"]) as src, open(target, "xb") as dst:
        written.append(target)
        shutil.copyfileobj(src, dst)
    with open(target, "rb") as f:
        sha, size = _stream_sha(f)
    if (sha, size) != (photo["sha256"], photo["bytes"]):
        raise ImportRefused(f"The copy of {photo['zip']} doesn't match its checksum.")
    return Attachment(family_id=family_id, learner_id=learner_id, file_name=name, media_type=tutor.MEDIA[photo["ext"]],
                      bytes=size, sha256=sha)


def apply_plan(db: Session, family: Family, plan: Plan, bundle: Bundle) -> tuple[dict[str, int], int]:
    """Write the plan in one transaction; returns (learner name -> id, the imports row's id)."""
    written: list[Path] = []
    try:
        lids: dict[int, int] = {}
        for pid, fields in plan.learners.items():
            lr = Learner(family_id=family.id, **fields)
            db.add(lr)
            db.flush()
            lids[pid] = lr.id
        for a in plan.access:
            db.add(ContentAccess(family_id=family.id, learner_id=lids[a["pid"]], **_fields(a)))
        for run_fields, rows in plan.runs:
            lid = lids[run_fields["pid"]]
            run = PracticeRun(family_id=family.id, learner_id=lid, **_fields(run_fields))
            run.results = [TaskResult(family_id=family.id, learner_id=lid, **r) for r in rows]
            db.add(run)
        for p in plan.progress:
            db.add(TopicProgress(family_id=family.id, learner_id=lids[p["pid"]], **_fields(p)))
        for chat_fields, messages in plan.chats:
            lid = lids[chat_fields["pid"]]
            chat = TutorChat(family_id=family.id, learner_id=lid, **_fields(chat_fields))
            db.add(chat)
            for m in messages:
                msg = TutorMessage(family_id=family.id, **m["fields"])
                if m["llm"]:
                    call = LlmCall(family_id=family.id, learner_id=lid, **m["llm"])
                    db.add(call)
                    db.flush()
                    msg.llm_call_id = call.id
                if m["photo"]:
                    msg.attachments.append(_copy_photo(bundle, family.id, lid, m["photo"], written))
                chat.messages.append(msg)
        learners = {plan.names[pid]: lid for pid, lid in lids.items()}
        record = DataImport(family_id=family.id, source=SOURCE, bundle_sha256=bundle.sha256, counts={
            "written": dict(plan.written), "skipped": {k: dict(v) for k, v in plan.skipped.items() if sum(v.values())},
            "learners": learners, "manifest": bundle.manifest["counts"],
            "schema_revision": bundle.manifest.get("schema_revision"), "exported_at": bundle.manifest.get("created_at")})
        db.add(record)
        db.commit()
        return learners, record.id
    except BaseException:
        db.rollback()
        for f in written:
            f.unlink(missing_ok=True)
        for folder in {f.parent for f in written}:
            try:
                folder.rmdir()  # only if empty
            except OSError:
                pass
        raise


# --------------------------------------------------------------------------- #
# The whole import
# --------------------------------------------------------------------------- #
@dataclass
class Report:
    dry_run: bool
    family: str
    bundle_sha256: str
    manifest: dict[str, Any]
    plan: Plan
    learners: dict[str, int | None]  # learner name -> new id (None in a dry run)
    import_id: int | None = None

    @property
    def balanced(self) -> bool:
        p = self.plan
        return all(p.source[src] == p.written[dst] + sum(p.skipped[src].values()) for src, dst in LEDGER)

    def lines(self) -> list[str]:
        p, m = self.plan, self.manifest
        out = [f"PitchDriven bundle: schema {m.get('schema_revision')}, exported {m.get('created_at')}, "
               f"sha256 {self.bundle_sha256}",
               f"Family '{self.family}': " + ", ".join(
                   f"{name} -> {'new learner' if lid is None else f'learner {lid}'}" for name, lid in self.learners.items()),
               f"  {'in the bundle':<28} {'imported as':<30}"]
        for src, dst in LEDGER:
            target = f"{p.written[dst]} {dst}"
            if dst == "tutor_messages":
                target += f", {p.written['llm_calls']} llm_calls"
            why = ", ".join(f"{n} {REASONS[r]}" for r, n in p.skipped[src].items() if n)
            out.append(f"  {p.source[src]:>6} {src:<21} {target:<30}" + (f" skipped: {why}" if why else ""))
        for missing in m.get("missing_photos", []):
            out.append(f"  Photo missing in PitchDriven already: message {missing['message_id']} ({missing['name']}).")
        out.extend(f"  Note: {n}" for n in p.notes)
        out.append("  Every bundle row is accounted for." if self.balanced
                   else "  WARNING: the counts don't add up; don't use this import before finding out why.")
        out.append("DRY RUN: nothing was written." if self.dry_run
                   else f"Imported (import #{self.import_id}). The same bundle can't be imported again.")
        return out


def import_bundle(db: Session, path: Path, family_slug: str, learner_names: list[str], *,
                  include_parent_tests: bool = False, dry_run: bool = False, content: Content | None = None) -> Report:
    names = [n.strip() for n in learner_names if n.strip()]
    if not names:
        raise ImportRefused("Name at least one learner (--learners Erik,Alan).")
    if len({_norm(n) for n in names}) != len(names):
        raise ImportRefused("A learner is named twice.")
    with open_bundle(path) as bundle:
        done = db.scalars(select(DataImport).where(DataImport.bundle_sha256 == bundle.sha256)).first()
        if done is not None:
            raise ImportRefused(f"This bundle was already imported (import #{done.id} on {done.imported_at:%Y-%m-%d %H:%M}).")
        family = db.scalars(select(Family).where(Family.slug == family_slug.strip().lower())).first()
        if family is None:
            raise ImportRefused(f"No family '{family_slug}'. Create it first with python -m app.manage create-family.")
        existing = {_norm(n) for n in db.scalars(select(Learner.name).where(Learner.family_id == family.id))}
        clash = [n for n in names if _norm(n) in existing]
        if clash:
            raise ImportRefused(f"The family already has a learner called {', '.join(clash)}. The import creates the "
                                "learners itself: remove or rename the existing one first.")
        if content is None:
            try:
                content = registry.get_content()
            except ContentError as exc:
                raise ImportRefused(f"The topic files have problems, fix them first.\n{exc}") from None
        first_sort = (db.scalar(select(func.max(Learner.sort_order)).where(Learner.family_id == family.id)) or 0) + 1
        plan = build_plan(bundle, names, content, family.slug, include_parent_tests, first_sort)
        report = Report(dry_run=dry_run, family=family.slug, bundle_sha256=bundle.sha256, manifest=bundle.manifest,
                        plan=plan, learners={name: None for name in plan.names.values()})
        if dry_run:
            db.rollback()  # end the read transaction; nothing was added
            return report
        report.learners, report.import_id = apply_plan(db, family, plan, bundle)
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.importers.pitchdriven", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bundle", type=Path, help="the zip made by scripts/export_pitchdriven_study.py")
    parser.add_argument("--family", required=True, help="the family's slug (it must exist)")
    parser.add_argument("--learners", required=True, help="PitchDriven player names, comma-separated (Erik,Alan)")
    parser.add_argument("--include-parent-tests", action="store_true", help="also import the parent's own Foxy test chats")
    parser.add_argument("--dry-run", action="store_true", help="check and count everything, write nothing")
    args = parser.parse_args(argv)

    from ..db import SessionLocal
    from ..migrate import run_migrations

    run_migrations()
    with SessionLocal() as db:
        try:
            report = import_bundle(db, args.bundle, args.family, args.learners.split(","),
                                   include_parent_tests=args.include_parent_tests, dry_run=args.dry_run)
        except ImportRefused as exc:
            print(f"Import refused: {exc}", file=sys.stderr)
            return 1
    print("\n".join(report.lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
