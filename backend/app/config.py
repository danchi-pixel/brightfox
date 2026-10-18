"""Application configuration.

Everything can be overridden with UCILNICA_* environment variables, so tests and the server can relocate
data without touching code. By default all data lives in ``<project>/data``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

APP_NAME = "BrightFox"
APP_VERSION = "0.1.0"


@dataclass
class Settings:
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 7687
    allowed_hosts: list[str] = field(default_factory=lambda: ["localhost", "127.0.0.1", "[::1]", "testserver"])
    cookie_secure: bool = False  # session cookie only over HTTPS (on in production)
    session_days: int = 30
    behind_proxy: bool = False  # trust X-Forwarded-* from the reverse proxy (Caddy)
    static_dir: Path | None = None  # serve the built web app from here (single-container deployment)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ucilnica.db"

    @property
    def files_dir(self) -> Path:
        """Photos the kids send to Foxy, per family and learner. Never served publicly."""
        return self.data_dir / "files"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.files_dir, self.tmp_dir, self.backups_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("UCILNICA_DATA_DIR", PROJECT_DIR / "data")).resolve()
    s = Settings(data_dir=data_dir)
    s.host = os.environ.get("UCILNICA_API_HOST", s.host)
    s.port = int(os.environ.get("UCILNICA_API_PORT", s.port))
    extra_hosts = os.environ.get("UCILNICA_ALLOWED_HOSTS", "")
    if extra_hosts:
        s.allowed_hosts.extend(h.strip() for h in extra_hosts.split(",") if h.strip())
    s.cookie_secure = _flag("UCILNICA_COOKIE_SECURE")
    s.behind_proxy = _flag("UCILNICA_BEHIND_PROXY")
    s.session_days = int(os.environ.get("UCILNICA_SESSION_DAYS", s.session_days))
    static = os.environ.get("UCILNICA_STATIC_DIR")
    s.static_dir = Path(static).resolve() if static else None
    return s


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


settings = load_settings()
