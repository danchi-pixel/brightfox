"""Export PitchDriven's Study data into a bundle for Učilnica (a one-off, for the move).

Standard library only (Python 3.12), so it runs inside the PitchDriven container as it is, fed on stdin:

    python - --db /data/football7676.db --data /data --out /data/tmp/study-export.zip < export_pitchdriven_study.py

It never writes to the database: it takes an online-backup snapshot (sqlite3 backup API) into a temporary
file and reads only that. It refuses a database older than revision 0013, or a later one whose Study tables
changed. The bundle is a zip with:

- ``manifest.json``: schema revision, row counts per table, sha256 of every table file and every photo,
  photos that messages name but that are missing on disk, and ``created_at``;
- ``tables/<table>.json``: study_profiles, study_approvals, study_attempts, study_progress, study_chats,
  study_messages; the players those rows (or kid accounts) refer to; and every account's username, role,
  player_id and language. **Never password hashes or sign-in sessions**;
- ``photos/<player_id>/<name>``: the chat photos from ``<data>/study/<player_id>/``.

The zip holds the kids' chats: it is written with owner-only permissions. Delete it after the import.
Učilnica reads it with ``python -m app.importers.pitchdriven`` (see docs/import.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

FORMAT = 1
MIN_REVISION = 13  # 0013 added study_progress, the last Study table

# The columns read from each table, nothing else. Users: no password hash, no dates, no sessions.
STUDY_TABLES: dict[str, list[str]] = {
    "study_profiles": ["player_id", "grade", "tutor_enabled", "daily_limit", "notes", "updated_at"],
    "study_approvals": ["set_id", "version", "player_ids", "approved_at"],
    "study_attempts": ["id", "player_id", "set_id", "version", "results", "finished", "challenge", "local_date",
                       "created_at"],
    "study_progress": ["player_id", "set_id", "known", "goals", "updated_at"],
    "study_chats": ["id", "player_id", "subject", "title", "parent_test", "created_at", "updated_at"],
    "study_messages": ["id", "chat_id", "role", "text", "image", "model", "input_tokens", "output_tokens",
                       "cache_read_tokens", "cache_write_tokens", "cost_usd", "local_date", "created_at"],
}
PEOPLE_TABLES: dict[str, list[str]] = {
    "players": ["id", "name", "avatar", "color", "role", "archived"],
    "users": ["username", "role", "player_id", "language"],
}
JSON_COLUMNS = {"player_ids", "results", "known", "goals"}
BOOL_COLUMNS = {"tutor_enabled", "finished", "challenge", "parent_test", "archived"}
# PitchDriven names photos <uuid hex>.<jpg|png|webp>; anything else in the folder is left behind.
PHOTO_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,58}\.(jpg|jpeg|png|webp)")


class ExportError(Exception):
    """The export can't go ahead (the message says why). Nothing was written."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(db_path: Path, target: Path) -> None:
    """A consistent copy of a live database (the app may keep writing while this runs)."""
    if not db_path.is_file():  # sqlite3.connect would quietly create an empty database
        raise ExportError(f"No database at {db_path}.")
    src = sqlite3.connect(str(db_path), timeout=30)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def check_schema(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.DatabaseError:
        raise ExportError("This isn't a PitchDriven database (no alembic_version table).") from None
    rev = row[0] if row else None
    if not rev or not str(rev).isdigit() or int(rev) < MIN_REVISION:
        raise ExportError(f"The database is at revision {rev!r}; the export needs 0013 or later.")
    for table, cols in {**STUDY_TABLES, **PEOPLE_TABLES}.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        missing = [c for c in cols if c not in have]
        if not have or missing:
            raise ExportError(f"Revision {rev} changed the table {table} (missing: {', '.join(missing) or 'the table'}); "
                              "update this exporter before using it.")
    return str(rev)


def _clean(col: str, value):
    if value is None:
        return None
    if col in JSON_COLUMNS:
        return json.loads(value) if isinstance(value, str) else value
    if col in BOOL_COLUMNS:
        return bool(value)
    if isinstance(value, bytes):
        raise ExportError(f"Unexpected binary value in column {col}.")
    return value


def read_rows(conn: sqlite3.Connection, table: str, cols: list[str]) -> list[dict]:
    cur = conn.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY rowid")
    return [{c: _clean(c, v) for c, v in zip(cols, row)} for row in cur]


def collect(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    tables = {t: read_rows(conn, t, cols) for t, cols in STUDY_TABLES.items()}
    users = read_rows(conn, "users", PEOPLE_TABLES["users"])
    # Only the players Study (or a kid's account) refers to; everything football stays behind.
    pids = {r["player_id"] for t in ("study_profiles", "study_attempts", "study_progress", "study_chats")
            for r in tables[t]}
    pids |= {int(p) for a in tables["study_approvals"] for p in (a["player_ids"] or [])}
    pids |= {u["player_id"] for u in users if u["role"] == "player" and u["player_id"] is not None}
    tables["players"] = [p for p in read_rows(conn, "players", PEOPLE_TABLES["players"]) if p["id"] in pids]
    tables["users"] = users
    return tables


def find_photos(data_dir: Path, tables: dict[str, list[dict]]) -> tuple[dict[str, Path], list[dict], int]:
    """(zip name -> file) for the exported players' photo folders, photos that messages name but are missing,
    and the number of other files left behind."""
    found: dict[str, Path] = {}
    left = 0
    for pid in sorted(p["id"] for p in tables["players"]):
        folder = data_dir / "study" / str(pid)
        if not folder.is_dir() or folder.is_symlink():
            continue
        for f in sorted(folder.iterdir()):
            if f.is_file() and not f.is_symlink() and PHOTO_NAME.fullmatch(f.name):
                found[f"photos/{pid}/{f.name}"] = f
            else:
                left += 1
    chat_player = {c["id"]: c["player_id"] for c in tables["study_chats"]}
    missing = [{"message_id": m["id"], "player_id": chat_player.get(m["chat_id"]), "name": m["image"]}
               for m in tables["study_messages"]
               if m["image"] and f"photos/{chat_player.get(m['chat_id'])}/{m['image']}" not in found]
    return found, missing, left


def write_bundle(out: Path, revision: str, tables: dict[str, list[dict]], photos: dict[str, Path],
                 missing: list[dict]) -> dict:
    manifest: dict = {
        "format": FORMAT,
        "source": "pitchdriven",
        "schema_revision": revision,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "counts": {t: len(rows) for t, rows in tables.items()} | {"photos": len(photos)},
        "tables": {},
        "photos": {},
        "missing_photos": missing,
    }
    partial = out.with_name(out.name + ".partial")
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for table, rows in tables.items():
            data = json.dumps(rows, ensure_ascii=False, indent=1).encode("utf-8")
            name = f"tables/{table}.json"
            zf.writestr(name, data)
            manifest["tables"][table] = {"file": name, "sha256": _sha256(data)}
        for name, path in photos.items():
            data = path.read_bytes()
            zf.writestr(name, data, compress_type=zipfile.ZIP_STORED)  # photos are compressed already
            manifest["photos"][name] = {"sha256": _sha256(data), "bytes": len(data)}
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    os.chmod(partial, 0o600)
    os.replace(partial, out)
    return manifest


def export(db: Path, data_dir: Path, out: Path) -> tuple[dict, int]:
    """Write the bundle; returns its manifest and the number of other files left in the photo folders."""
    if out.exists():
        raise ExportError(f"{out} already exists; move or delete it first.")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="study-export-", dir=out.parent) as tmp:
        snap = Path(tmp) / "snapshot.db"
        snapshot(db, snap)
        conn = sqlite3.connect(str(snap))
        try:
            revision = check_schema(conn)
            tables = collect(conn)
        finally:
            conn.close()
    photos, missing, left = find_photos(data_dir, tables)
    return write_bundle(out, revision, tables, photos, missing), left


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="export_pitchdriven_study.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, type=Path, help="PitchDriven's database (football7676.db)")
    parser.add_argument("--data", required=True, type=Path, help="PitchDriven's data folder (holds study/<player id>/)")
    parser.add_argument("--out", required=True, type=Path, help="the zip to write (must not exist yet)")
    args = parser.parse_args(argv)
    try:
        m, left = export(args.db, args.data, args.out)
    except ExportError as exc:
        print(f"Export refused: {exc}", file=sys.stderr)
        return 1
    c = m["counts"]
    print(f"Exported PitchDriven Study data (schema {m['schema_revision']}, {m['created_at']}):")
    for table in (*STUDY_TABLES, *PEOPLE_TABLES):
        print(f"  {table:<16} {c[table]:>6}")
    print(f"  {'photos':<16} {c['photos']:>6}")
    if m["missing_photos"]:
        print(f"  WARNING: {len(m['missing_photos'])} photo(s) named in messages are missing on disk (listed in the manifest).")
    if left:
        print(f"  Note: {left} other file(s) in the photo folders were left behind.")
    data = args.out.read_bytes()
    print(f"Wrote {args.out} ({len(data) / 1024:.0f} KB, sha256 {_sha256(data)}).")
    print("It holds the kids' chats: copy it straight to Ucilnica, then delete it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
