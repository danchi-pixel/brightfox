"""Programmatic Alembic upgrade (run at startup and after restoring a backup)."""
from __future__ import annotations

from alembic import command
from alembic.config import Config

from .config import BACKEND_DIR


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logging"] = False
    return cfg


def run_migrations() -> None:
    command.upgrade(alembic_config(), "head")


def current_revision() -> str | None:
    from sqlalchemy import text

    from .db import engine

    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        return None
