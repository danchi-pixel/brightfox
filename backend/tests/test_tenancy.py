"""Families never see each other.

1. Route audit: every /api route depends on exactly one access dependency (public, self, admin, learner).
2. Isolation sweep: every parent and learner route, called with ids that belong to another family (or, for
   a kid, to another learner), answers 404. New routes are swept automatically.
"""
from __future__ import annotations

import re

from fastapi.routing import APIRoute

from app.access import ACCESS_DEPENDENCIES, admin_ctx, learner_in_scope
from app.main import app

from .conftest import Fam


def _calls(dependant) -> list:
    out = []
    for d in dependant.dependencies:
        out.append(d.call)
        out.extend(_calls(d))
    return out


def _api_routes() -> list[APIRoute]:
    return [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api")]


def test_every_route_has_exactly_one_access_rule():
    problems = []
    for r in _api_routes():
        found = [c for c in _calls(r.dependant) if c in ACCESS_DEPENDENCIES]
        if len(set(found)) != 1:
            problems.append(f"{sorted(r.methods)} {r.path}: {[c.__name__ for c in found]}")
    assert not problems, "\n".join(problems)


def _fill(path: str, values: dict[str, object]) -> str:
    return re.sub(r"{(\w+)(:[^}]*)?}", lambda m: str(values.get(m.group(1), "x")), path)


def _routes_with(dep) -> list[tuple[str, str]]:
    out = []
    for r in _api_routes():
        if dep in _calls(r.dependant):
            out.extend((m, r.path) for m in sorted(r.methods) if m != "HEAD")
    return out


def _call(client, method: str, url: str):
    return client.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)


def test_parent_cannot_reach_another_familys_learners(fam_a: Fam, fam_b: Fam):
    foreign = {"lid": fam_b.learners["Cene"], "uid": fam_b.kid_user_ids["Cene"]}
    for method, path in _routes_with(learner_in_scope):
        url = _fill(path, foreign)
        assert _call(fam_a.admin, method, url).status_code == 404, f"{method} {url}"
    # Family routes that take an id refuse another family's objects too.
    for method, path in _routes_with(admin_ctx):
        if "{" in path:
            url = _fill(path, {"lid": foreign["lid"], "uid": foreign["uid"]})
            assert _call(fam_a.admin, method, url).status_code == 404, f"{method} {url}"


def test_learner_cannot_reach_a_sibling(fam_a: Fam):
    sibling = {"lid": fam_a.learners["Bor"]}
    for method, path in _routes_with(learner_in_scope):
        url = _fill(path, sibling)
        assert _call(fam_a.kids["Ana"], method, url).status_code == 404, f"{method} {url}"


def test_parent_sees_only_their_family(fam_a: Fam, fam_b: Fam):
    names = {lr["name"] for lr in fam_a.admin.get("/api/family").json()["learners"]}
    assert "Cene" not in names and {"Ana", "Bor"} <= names
    accounts = {a["username"] for a in fam_b.admin.get("/api/family/accounts").json()}
    assert accounts == {"fam-b-parent", "fam-b-cene"}
