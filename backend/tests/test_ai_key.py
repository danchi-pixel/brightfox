"""Foxy's API key in the app: parents set, check and remove it; kids can't; the key never comes back.

Scratch data only, and the "Test key" check is a fake (the API is never called from tests).
"""
from __future__ import annotations

import os
import stat
import sys

import pytest

from app.config import settings
from app.llm import anthropic_provider, api_key
from app.llm import service as llm_service

from .conftest import Fam

FAKE_KEY = "sk-ant-api03-" + "Test_key-" * 4 + "wxyz"  # made up; never a real key


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(settings, "ai_key_families", None)
    api_key.remove()
    yield
    api_key.remove()
    llm_service.set_test_key_check(None)


def test_parent_sets_reads_and_removes_the_key(fam_a: Fam):
    r = fam_a.admin.get("/api/family/ai/key")
    assert r.status_code == 200
    assert r.json()["configured"] is False and r.json()["source"] == "none"

    r = fam_a.admin.put("/api/family/ai/key", json={"key": f"  {FAKE_KEY}\n"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["configured"] is True and body["source"] == "app" and body["hint"] == "wxyz"
    assert body["updated_at"]
    assert FAKE_KEY not in r.text
    assert api_key.key_path().read_text(encoding="ascii") == FAKE_KEY
    assert anthropic_provider.configured()
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(api_key.key_path()).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(api_key.key_path().parent).st_mode) == 0o700

    r = fam_a.admin.get("/api/family/ai/key")
    assert FAKE_KEY not in r.text and r.json()["hint"] == "wxyz"

    r = fam_a.admin.delete("/api/family/ai/key")
    assert r.status_code == 200 and r.json()["source"] == "none"
    assert not api_key.key_path().exists()
    assert not anthropic_provider.configured()


def test_app_key_wins_and_falls_back_to_the_server_key(fam_a: Fam, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-server-key-" + "s" * 10 + "1234")
    r = fam_a.admin.get("/api/family/ai/key").json()
    assert r["source"] == "server" and r["hint"] == "1234"
    fam_a.admin.put("/api/family/ai/key", json={"key": FAKE_KEY})
    assert api_key.current() == (FAKE_KEY, "app")
    fam_a.admin.delete("/api/family/ai/key")
    assert api_key.current()[1] == "server"


def test_the_client_follows_a_changed_key(fam_a: Fam):
    fam_a.admin.put("/api/family/ai/key", json={"key": FAKE_KEY})
    first = anthropic_provider._client()
    assert anthropic_provider._client() is first
    fam_a.admin.put("/api/family/ai/key", json={"key": FAKE_KEY[:-4] + "abcd"})
    second = anthropic_provider._client()
    assert second is not first and second.api_key.endswith("abcd")


@pytest.mark.parametrize("bad", ["", "hello", "sk-proj-abcdefghijklmnopqrstuvwxyz", "sk-ant-has space in it xxxxxx",
                                 "sk-ant-" + "x" * 400, "sk-ant-abc$%^&*()abcdefghijk"])
def test_invalid_keys_are_rejected(fam_a: Fam, bad: str):
    r = fam_a.admin.put("/api/family/ai/key", json={"key": bad})
    assert r.status_code in (400, 422)
    if bad:
        assert bad not in r.text
    assert not api_key.key_path().exists()


def test_kids_cannot_see_or_change_the_key(fam_a: Fam):
    fam_a.admin.put("/api/family/ai/key", json={"key": FAKE_KEY})
    kid = fam_a.kids["Ana"]
    for method, url in [("GET", "/api/family/ai/key"), ("PUT", "/api/family/ai/key"),
                        ("DELETE", "/api/family/ai/key"), ("POST", "/api/family/ai/key/test")]:
        r = kid.request(method, url, json={"key": FAKE_KEY[:-4] + "kids"} if method == "PUT" else None)
        assert r.status_code in (403, 404), f"{method} {url}"
        assert "wxyz" not in r.text
    assert api_key.current() == (FAKE_KEY, "app")


def test_test_button_uses_the_fake_check(fam_a: Fam):
    llm_service.set_test_key_check(lambda: "auth")
    r = fam_a.admin.post("/api/family/ai/key/test")
    assert r.status_code == 200 and r.json() == {"result": "auth", "ok": False, "message": r.json()["message"]}
    llm_service.set_test_key_check(lambda: "ok")
    assert fam_a.admin.post("/api/family/ai/key/test").json()["ok"] is True


def test_only_owner_families_manage_the_key(fam_a: Fam, fam_b: Fam, monkeypatch):
    monkeypatch.setattr(settings, "ai_key_families", ["fam-a"])
    assert fam_a.admin.put("/api/family/ai/key", json={"key": FAKE_KEY}).status_code == 200
    r = fam_b.admin.get("/api/family/ai/key")
    assert r.status_code == 200
    assert r.json() == {"configured": True, "source": "app", "can_manage": False, "hint": None, "updated_at": None}
    assert fam_b.admin.put("/api/family/ai/key", json={"key": FAKE_KEY[:-4] + "bbbb"}).status_code == 403
    assert fam_b.admin.delete("/api/family/ai/key").status_code == 403
    assert fam_b.admin.post("/api/family/ai/key/test").status_code == 403
    assert api_key.current() == (FAKE_KEY, "app")
