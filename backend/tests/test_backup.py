"""Backups (app/backup.py and ``manage backup``), each on its own scratch data folder."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import zipfile
from datetime import datetime, timedelta

import pytest

from app import backup, manage
from app.config import Settings, settings


@pytest.fixture()
def scratch(tmp_path) -> Settings:
    cfg = Settings(data_dir=tmp_path / "data")
    cfg.ensure_dirs()
    return cfg


def _make_db(cfg: Settings, rows: int = 3) -> sqlite3.Connection:
    """A small WAL database like the app's; the connection stays open, so the rows are still in the -wal file."""
    con = sqlite3.connect(str(cfg.db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT)")
    con.executemany("INSERT INTO notes (text) VALUES (?)", [(f"note {i}",) for i in range(rows)])
    con.commit()
    return con


def test_backup_contains_db_and_files(scratch, tmp_path):
    con = _make_db(scratch)
    photo = scratch.files_dir / "1" / "7" / "abc.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"\xff\xd8 jpeg bytes")
    (scratch.files_dir / "2" / "9").mkdir(parents=True)
    (scratch.files_dir / "2" / "9" / "x.png").write_bytes(b"png")
    (scratch.backups_dir / "old.zip").write_bytes(b"not part of a backup")
    (scratch.tmp_dir / "upload.part").write_bytes(b"not part of a backup")
    try:
        made = backup.create_backup("daily", scratch)
    finally:
        con.close()

    path = made["path"]
    assert path.parent == scratch.backups_dir
    assert backup.NAME_RE.fullmatch(path.name) and path.name.endswith("-daily.zip")
    with zipfile.ZipFile(path) as z:
        assert set(z.namelist()) == {"manifest.json", "ucilnica.db", "files/1/7/abc.jpg", "files/2/9/x.png"}
        assert z.read("files/1/7/abc.jpg") == b"\xff\xd8 jpeg bytes"
        manifest = json.loads(z.read("manifest.json"))
        (tmp_path / "restored.db").write_bytes(z.read("ucilnica.db"))
    assert manifest["app"] == "BrightFox" and manifest["label"] == "daily"
    assert manifest["counts"] == {"notes": 3} and manifest["files"] == 2

    restored = sqlite3.connect(str(tmp_path / "restored.db"))
    try:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 3
    finally:
        restored.close()
    # Nothing left behind but the zip.
    assert sorted(p.name for p in scratch.tmp_dir.iterdir()) == ["upload.part"]
    assert not list(scratch.backups_dir.glob("*.partial"))
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_backup_without_files_folder_or_database(scratch):
    with pytest.raises(backup.BackupError):
        backup.create_backup("daily", scratch)  # no database yet
    _make_db(scratch, rows=1).close()
    scratch.files_dir.rmdir()
    with zipfile.ZipFile(backup.create_backup("weekly", scratch)["path"]) as z:
        assert set(z.namelist()) == {"manifest.json", "ucilnica.db"}
    with pytest.raises(backup.BackupError):
        backup.create_backup("Bad Label", scratch)


def test_prune_keeps_the_newest_n_of_one_label(scratch):
    _make_db(scratch, rows=1).close()
    start = datetime(2026, 10, 1, 4, 15)
    daily = [backup.create_backup("daily", scratch, now=start + timedelta(days=i))["name"] for i in range(5)]
    weekly = [backup.create_backup("weekly", scratch, now=start + timedelta(days=7 * i, minutes=15))["name"] for i in range(2)]
    other = scratch.backups_dir / "notes.txt"
    other.write_text("kept")

    removed = backup.prune("daily", 2, scratch)

    assert sorted(removed) == sorted(daily[:3])
    left = sorted(p.name for p in scratch.backups_dir.iterdir())
    assert left == sorted(daily[3:] + weekly + ["notes.txt"])
    assert backup.prune("daily", 2, scratch) == []
    with pytest.raises(backup.BackupError):
        backup.prune("daily", 0, scratch)


def test_manage_backup_command(client, capsys):
    # The session's scratch data folder (conftest), which the app's startup migrated.
    assert manage.main(["backup", "--label", "manage-test", "--keep", "1"]) == 0
    made = [p for p in settings.backups_dir.glob("ucilnica-backup-*-manage-test.zip")]
    assert len(made) == 1 and made[0].name in capsys.readouterr().out
    with zipfile.ZipFile(made[0]) as z:
        counts = json.loads(z.read("manifest.json"))["counts"]
    assert "families" in counts and "learners" in counts
    made[0].unlink()
    assert manage.main(["backup", "--label", "Not OK"]) == 1
