from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.db import SessionLocal
from app.main import app
from app.models import Family

from .conftest import Fam, make_family, new_password, sign_in


def test_health_and_status_are_public(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert TestClient(app).get("/api/auth/status").json() == {"authenticated": False}


def test_everything_else_needs_a_session(client):
    anon = TestClient(app)
    for path in ("/api/family", "/api/family/accounts", "/api/learners/1/home", "/docs", "/openapi.json"):
        assert anon.get(path).status_code == 401, path


def test_login_and_status(fam_a: Fam):
    me = fam_a.admin.get("/api/auth/status").json()
    assert me["authenticated"] and me["role"] == "admin" and me["family"]["id"] == fam_a.id
    kid = fam_a.kids["Ana"].get("/api/auth/status").json()
    assert kid["role"] == "learner" and kid["learner_id"] == fam_a.learners["Ana"] and kid["learner_name"] == "Ana"
    assert kid["language"] == "sl"


def test_wrong_password_and_rate_limit(fam_a: Fam):
    auth.limiter.reset()
    c = TestClient(app)
    for _ in range(5):
        assert c.post("/api/auth/login", json={"username": "fam-a-parent", "password": "wrong-password"}).status_code == 401
    assert c.post("/api/auth/login", json={"username": "fam-a-parent", "password": "wrong-password"}).status_code == 429
    auth.limiter.reset()


def test_learner_is_fenced_in(fam_a: Fam):
    kid = fam_a.kids["Ana"]
    assert kid.get("/api/family").status_code == 404
    assert kid.get("/api/family/accounts").status_code == 404
    assert kid.post("/api/family/learners", json={"name": "X"}).status_code == 404
    # Another learner's space, even in the same family, doesn't exist for this kid.
    assert kid.get(f"/api/learners/{fam_a.learners['Bor']}/home").status_code == 404
    # Self-service works.
    assert kid.put("/api/auth/preferences", json={"language": "en"}).json()["language"] == "en"
    assert kid.put("/api/auth/preferences", json={"language": None}).json()["language"] == "sl"


def test_parent_manages_learners_and_accounts(fam_a: Fam):
    a = fam_a.admin
    lr = a.post("/api/family/learners", json={"name": " Zala ", "grade": 3, "rhythm": {"days": [5, 1, 1, 9], "minutes": 15}}).json()
    assert lr["name"] == "Zala" and lr["rhythm"] == {"days": [1, 5], "minutes": 15}
    lr = a.patch(f"/api/family/learners/{lr['id']}", json={"grade": None, "interests": "nogomet"}).json()
    assert lr["grade"] is None and lr["interests"] == "nogomet"
    pw = new_password()
    acc = a.post("/api/family/accounts", json={"username": "fam-a-zala", "password": pw, "role": "learner",
                                               "learner_id": lr["id"]}).json()
    assert acc["learner_name"] == "Zala"
    # One account per learner; parent accounts aren't linked to a learner.
    assert a.post("/api/family/accounts", json={"username": "fam-a-zala2", "password": pw, "role": "learner",
                                                "learner_id": lr["id"]}).status_code == 400
    assert a.post("/api/family/accounts", json={"username": "fam-a-x", "password": pw, "role": "admin",
                                                "learner_id": lr["id"]}).status_code == 400
    assert a.post("/api/family/accounts", json={"username": "fam-a-y", "password": "short", "role": "admin"}).status_code == 400
    zala = sign_in("fam-a-zala", pw)
    # A new password from the parent signs that account out everywhere.
    assert a.patch(f"/api/family/accounts/{acc['id']}", json={"password": new_password()}).status_code == 200
    assert zala.get("/api/auth/status").json() == {"authenticated": False}
    assert a.delete(f"/api/family/accounts/{acc['id']}").json() == {"deleted": acc["id"]}
    me = a.get("/api/auth/status").json()
    assert a.delete(f"/api/family/accounts/{fam_a.admin_user_id}").status_code == 400
    assert me["authenticated"]


def test_change_password_signs_out_other_devices(client):
    f = make_family("fam-pw", ["Pia"])
    other_device = sign_in("fam-pw-parent", f.passwords["fam-pw-parent"])
    new = new_password()
    r = f.admin.post("/api/auth/change-password", json={"current_password": f.passwords["fam-pw-parent"], "new_password": new})
    assert r.json() == {"changed": True}
    assert f.admin.get("/api/family").status_code == 200  # this device got a fresh session
    assert other_device.get("/api/family").status_code == 401
    assert f.admin.post("/api/auth/change-password", json={"current_password": "nope", "new_password": new}).status_code == 400


def test_suspended_family_is_signed_out(client):
    f = make_family("fam-sus", ["Sara"])
    with SessionLocal() as db:
        fam = db.get(Family, f.id)
        fam.status = "suspended"
        db.commit()
    auth._cache.clear()
    assert f.admin.get("/api/family").status_code == 401
    assert f.kids["Sara"].get("/api/auth/status").json() == {"authenticated": False}
    auth.limiter.reset()
    r = TestClient(app).post("/api/auth/login", json={"username": "fam-sus-parent", "password": f.passwords["fam-sus-parent"]})
    assert r.status_code == 401


def test_learner_account_must_be_in_the_same_family(fam_a: Fam, fam_b: Fam):
    with SessionLocal() as db, pytest.raises(ValueError):
        auth.create_account(db, fam_a.id, "fam-a-thief", new_password(), role="learner", learner_id=fam_b.learners["Cene"])
