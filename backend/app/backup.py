"""Backups of the database and the stored files (homework photos) as one .zip.

    data/backups/ucilnica-backup-<YYYYmmdd-HHMMSS>-<label>.zip      (mode 600)
        manifest.json   app, version, time, label, row count per table, number of files
        ucilnica.db     a consistent copy made with SQLite's online backup API (safe while the app runs)
        files/...       everything under data/files/ (<family id>/<learner id>/<photo>)

The server makes them with ``python -m app.manage backup --label daily --keep 14`` (deploy/server/backup.sh).
To restore: stop the app and unpack the zip into the data folder (deploy/DEPLOYMENT.md).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_NAME, APP_VERSION, Settings, settings

DB_ENTRY = "ucilnica.db"
MANIFEST_ENTRY = "manifest.json"
FILES_PREFIX = "files/"
LABEL_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,29}")
NAME_RE = re.compile(r"ucilnica-backup-\d{8}-\d{6}-([a-z0-9][a-z0-9-]{0,29})\.zip")


class BackupError(Exception):
    """A problem to show as is (no database yet, a bad label)."""


def _snapshot(db_path: Path, dest: Path) -> None:
    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _row_counts(db_file: Path) -> dict[str, int]:
    con = sqlite3.connect(str(db_file))
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    finally:
        con.close()


def _remove_db_files(path: Path) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(path) + suffix).unlink(missing_ok=True)


def create_backup(label: str, cfg: Settings | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Write one backup zip into the backups folder and return its name, path, size and manifest."""
    cfg = cfg or settings
    if not LABEL_RE.fullmatch(label):
        raise BackupError("Use a-z, 0-9 and - for the label (at most 30 characters).")
    if not cfg.db_path.is_file():
        raise BackupError(f"There is no database at {cfg.db_path} yet.")
    cfg.ensure_dirs()
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    final = cfg.backups_dir / f"ucilnica-backup-{stamp}-{label}.zip"
    if final.exists():
        raise BackupError(f"{final.name} already exists.")
    partial = final.with_name(final.name + ".partial")
    snap = cfg.tmp_dir / f"backup-{uuid.uuid4().hex}.db"
    try:
        _snapshot(cfg.db_path, snap)
        files = sorted(p for p in cfg.files_dir.rglob("*") if p.is_file()) if cfg.files_dir.is_dir() else []
        manifest = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "label": label,
            "counts": _row_counts(snap),
            "files": len(files),
            "files_bytes": sum(p.stat().st_size for p in files),
        }
        # Created with mode 600 from the start: the zip holds the kids' chats and photos.
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(fd, "wb") as fh, zipfile.ZipFile(fh, "w", allowZip64=True) as z:
            z.writestr(MANIFEST_ENTRY, json.dumps(manifest, indent=2, ensure_ascii=False))
            z.write(snap, DB_ENTRY, compress_type=zipfile.ZIP_DEFLATED)
            for p in files:
                # Photos are already compressed: store them as they are.
                z.write(p, FILES_PREFIX + p.relative_to(cfg.files_dir).as_posix(), compress_type=zipfile.ZIP_STORED)
        os.chmod(partial, 0o600)
        os.replace(partial, final)
    finally:
        _remove_db_files(snap)
        partial.unlink(missing_ok=True)
    return {"name": final.name, "path": final, "size_bytes": final.stat().st_size, "manifest": manifest}


def prune(label: str, keep: int, cfg: Settings | None = None) -> list[str]:
    """Delete all but the newest ``keep`` backups made with exactly this label; return the deleted names."""
    cfg = cfg or settings
    if keep < 1:
        raise BackupError("--keep must be at least 1.")
    if not cfg.backups_dir.is_dir():
        return []
    mine = []
    for p in cfg.backups_dir.iterdir():
        m = NAME_RE.fullmatch(p.name)
        if m and m.group(1) == label:
            mine.append(p)
    mine.sort(key=lambda p: p.name, reverse=True)  # the time stamp in the name sorts oldest last
    removed = []
    for p in mine[keep:]:
        p.unlink(missing_ok=True)
        removed.append(p.name)
    return removed
