"""Test setup: every test session uses a fresh, temporary data folder and scratch families.

Never the real data folder, never real accounts, never the AI (see CLAUDE.md).
"""
from __future__ import annotations

import os
import secrets
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="ucilnica-test-"))
os.environ["UCILNICA_DATA_DIR"] = str(_TMP / "data")
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("UCILNICA_LOCAL_FAMILY", None)  # tests enable this explicitly with monkeypatch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app.config import PROJECT_DIR, settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Family, Learner, User  # noqa: E402

assert settings.data_dir != (PROJECT_DIR / "data").resolve(), "tests must never use the real data folder"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    shutil.rmtree(_TMP, ignore_errors=True)


def new_password() -> str:
    return "t-" + secrets.token_urlsafe(12)


def sign_in(username: str, password: str) -> TestClient:
    auth.limiter.reset()
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c


@dataclass
class Fam:
    """A scratch family: a parent client, and per learner its id and signed-in client."""

    id: int
    slug: str
    admin: TestClient
    admin_user_id: int
    learners: dict[str, int] = field(default_factory=dict)  # name -> learner id
    kids: dict[str, TestClient] = field(default_factory=dict)  # name -> signed-in learner client
    kid_user_ids: dict[str, int] = field(default_factory=dict)
    passwords: dict[str, str] = field(default_factory=dict)  # username -> password (scratch only)


def make_family(slug: str, learner_names: list[str]) -> Fam:
    passwords: dict[str, str] = {}
    with SessionLocal() as db:
        fam = Family(slug=slug, name=f"Scratch {slug}")
        db.add(fam)
        db.commit()
        learners = {}
        for i, name in enumerate(learner_names):
            lr = Learner(family_id=fam.id, name=name, grade=6, sort_order=i)
            db.add(lr)
            db.commit()
            learners[name] = lr.id
        pw = new_password()
        admin = auth.create_account(db, fam.id, f"{slug}-parent", pw, role="admin")
        passwords[admin.username] = pw
        kid_ids = {}
        for name, lid in learners.items():
            pw = new_password()
            u = auth.create_account(db, fam.id, f"{slug}-{name.lower()}", pw, role="learner", learner_id=lid)
            passwords[u.username] = pw
            kid_ids[name] = u.id
        fam_id, admin_id = fam.id, admin.id
    out = Fam(id=fam_id, slug=slug, admin=sign_in(f"{slug}-parent", passwords[f"{slug}-parent"]), admin_user_id=admin_id,
              learners=learners, kid_user_ids=kid_ids, passwords=passwords)
    for name in learners:
        out.kids[name] = sign_in(f"{slug}-{name.lower()}", passwords[f"{slug}-{name.lower()}"])
    return out


@pytest.fixture(scope="session")
def fam_a(client) -> Fam:
    return make_family("fam-a", ["Ana", "Bor"])


@pytest.fixture(scope="session")
def fam_b(client) -> Fam:
    return make_family("fam-b", ["Cene"])


@pytest.fixture(scope="session")
def dan(client) -> Fam:
    """A scratch family with the slug of the real one, so it sees the family's topics and mocks (scratch data
    only). Erik and Alan for the topic tests, Mia for the mock tests."""
    return make_family("danijel", ["Erik", "Alan", "Mia"])


def user_row(user_id: int) -> User:
    with SessionLocal() as db:
        return db.get(User, user_id)
