"""Where Foxy's Anthropic API key comes from.

A parent can enter the key in the app (AI settings). It is stored in ``<data dir>/secrets/anthropic_api_key``
(folder mode 700, file mode 600, written atomically) and wins over the server's ``ANTHROPIC_API_KEY`` from
``secrets.env``. Removing it in the app falls back to the server key.

The key is never logged, never returned by the API (only its last 4 characters) and never put into an error
message. It is not in the backups either: those hold only the database and ``files/``.

One key serves the whole installation. When ``UCILNICA_AI_KEY_FAMILIES`` is set (production), only parents
of those families may see the hint and change the key; other families' parents see only whether Foxy has one.
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ..config import settings

KEY_RE = re.compile(r"^sk-ant-[A-Za-z0-9_-]+$")
Source = Literal["app", "server", "none"]


def key_path() -> Path:
    return settings.data_dir / "secrets" / "anthropic_api_key"


def clean(raw: str) -> str | None:
    """The key without surrounding whitespace if it looks like an Anthropic key, else None."""
    key = (raw or "").strip()
    return key if 20 <= len(key) <= 300 and KEY_RE.fullmatch(key) else None


def _stored() -> str | None:
    try:
        return clean(key_path().read_text(encoding="ascii"))
    except (OSError, UnicodeError):
        return None


def current() -> tuple[str | None, Source]:
    """The key to use now and where it came from: the app's own file first, then the server env."""
    key = _stored()
    if key:
        return key, "app"
    env = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return (env, "server") if env else (None, "none")


def save(key: str) -> None:
    """Store a cleaned key (atomic, mode 600)."""
    if clean(key) != key:
        raise ValueError("not a valid key")
    folder = key_path().parent
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(folder, 0o700)
    except OSError:
        pass
    old_umask = os.umask(0o077)
    try:
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".key-", suffix=".tmp")  # mkstemp creates it 0600
        try:
            with os.fdopen(fd, "w", encoding="ascii") as f:
                f.write(key)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, key_path())
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    finally:
        os.umask(old_umask)


def remove() -> bool:
    try:
        key_path().unlink()
        return True
    except FileNotFoundError:
        return False


def may_manage(family_slug: str) -> bool:
    allowed = settings.ai_key_families
    return allowed is None or family_slug in allowed


def status(family_slug: str) -> dict[str, object]:
    key, source = current()
    out: dict[str, object] = {"configured": key is not None, "source": source, "can_manage": may_manage(family_slug),
                              "hint": None, "updated_at": None}
    if key and out["can_manage"]:
        out["hint"] = key[-4:]
        if source == "app":
            try:
                out["updated_at"] = datetime.fromtimestamp(key_path().stat().st_mtime, timezone.utc).isoformat()
            except OSError:
                pass
    return out
