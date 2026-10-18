"""Foxy with a fake AI provider (the real API is never called in tests)."""
from __future__ import annotations

import base64

import pytest

from app import llm
from app.db import SessionLocal
from app.llm import service as llm_service
from app.models import LlmCall

from .conftest import Fam, make_family

PRIMER = "2026-10-17-primer-ulomki"
# A 1×1 PNG.
PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082")).decode()


class FakeProvider:
    def __init__(self) -> None:
        self.requests: list[llm.LLMRequest] = []
        self.mode = "ok"

    def __call__(self, req: llm.LLMRequest, spec, effort: str) -> llm.LLMReply:
        self.requests.append(req)
        if self.mode == "busy":
            raise llm.LLMRateLimited("busy")
        if self.mode == "key":
            raise llm.LLMAuthError("no")
        n = sum(1 for t in req.turns if t.role == "user")
        return llm.LLMReply(text=f"Namig {n}: kaj naloga sprašuje?", model=spec.id, provider="fake",
                            refused=self.mode == "refuse", cut_off=False, input_tokens=1500, output_tokens=200,
                            cost_usd=0.01)


@pytest.fixture()
def fake():
    f = FakeProvider()
    llm_service.set_test_provider(f)
    yield f
    llm_service.set_test_provider(None)


@pytest.fixture(scope="module")
def fam(client) -> Fam:
    f = make_family("fam-sova", ["Eva", "Gal"])
    f.admin.patch(f"/api/family/learners/{f.learners['Eva']}", json={"tutor_daily_limit": 3, "interests": "košarka"})
    return f


def test_not_configured_without_a_key(fam: Fam):
    lid = fam.learners["Eva"]
    r = fam.kids["Eva"].post(f"/api/learners/{lid}/chats", json={"subject": "math", "text": "Pomoč"})
    assert r.status_code == 409 and "Foxy" in r.json()["detail"]


def test_chat_limit_photos_and_ledger(fam: Fam, fake: FakeProvider):
    lid = fam.learners["Eva"]
    eva = fam.kids["Eva"]
    r = eva.post(f"/api/learners/{lid}/chats", json={"subject": "math", "text": "Koliko je 3/4 od 8?", "images": [PNG]})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["can_send"] and out["left_today"] == 2 and out["messages"][1]["text"].startswith("Namig 1")
    assert "cost_usd" not in out["chat"]  # kids never see costs
    img = out["messages"][0]["images"][0]
    assert eva.get(img).status_code == 200 and eva.get(img).headers["content-type"] == "image/png"
    system = "\n".join(b.text for b in fake.requests[-1].system)
    assert "košarka" in system and "Eva" in system and "BrightFox" in system
    assert fake.requests[-1].turns[-1].images[0].media_type == "image/png"

    cid = out["chat"]["id"]
    assert eva.post(f"/api/learners/{lid}/chats/{cid}/messages", json={"text": "6?"}).json()["left_today"] == 1
    assert fake.requests[-1].turns[0].images  # earlier photos are sent again
    eva.post(f"/api/learners/{lid}/chats/{cid}/messages", json={"text": "Hvala"})
    r = eva.post(f"/api/learners/{lid}/chats/{cid}/messages", json={"text": "Še eno"})
    assert r.status_code == 429 and "dovolj" in r.json()["detail"]

    parent_view = fam.admin.get(f"/api/learners/{lid}/chats/{cid}").json()
    assert parent_view["chat"]["cost_usd"] == pytest.approx(0.03) and parent_view["can_send"] is False
    with SessionLocal() as db:
        calls = db.query(LlmCall).filter(LlmCall.learner_id == lid).all()
        assert len(calls) == 3 and {c.job for c in calls} == {"tutor_chat"} and calls[0].model == "claude-opus-5-5"


def test_parent_test_chat_is_hidden_from_the_kid(fam: Fam, fake: FakeProvider):
    lid = fam.learners["Gal"]
    r = fam.admin.post(f"/api/learners/{lid}/chats", json={"subject": "english", "text": "Test", "images": [PNG]})
    out = r.json()
    assert out["chat"]["parent_test"] is True
    assert fam.kids["Gal"].get(f"/api/learners/{lid}/chats").json() == []
    assert fam.kids["Gal"].get(f"/api/learners/{lid}/chats/{out['chat']['id']}").status_code == 404
    assert fam.kids["Gal"].get(out["messages"][0]["images"][0]).status_code == 404
    assert fam.kids["Gal"].delete(f"/api/learners/{lid}/chats/{out['chat']['id']}").status_code == 403
    assert fam.admin.delete(f"/api/learners/{lid}/chats/{out['chat']['id']}").json() == {"deleted": out["chat"]["id"]}


def test_topic_chat_knows_the_book(client, fake: FakeProvider):
    f = make_family("fam-topic", ["Iva"])
    lid = f.learners["Iva"]
    version = f.admin.get(f"/api/studio/topics/{PRIMER}").json()["version"]
    f.admin.put(f"/api/studio/topics/{PRIMER}/access", json={"version": version, "learner_ids": [lid]})
    topic = f.kids["Iva"].get(f"/api/learners/{lid}/topics/{PRIMER}").json()
    task = topic["tasks"][3]
    r = f.kids["Iva"].post(f"/api/learners/{lid}/chats", json={"topic_id": PRIMER, "task_id": task["id"], "text": "Ne vem"})
    assert r.status_code == 201 and r.json()["chat"]["topic_id"] == PRIMER and r.json()["chat"]["subject"] == "math"
    system = fake.requests[-1].system
    assert system[0].cache and system[1].cache and not system[2].cache
    assert topic["title"] in system[1].text and task["solution"] in system[1].text
    assert f.kids["Iva"].post(f"/api/learners/{lid}/chats", json={"topic_id": PRIMER, "task_id": "nope", "text": "x"}).status_code == 400
    assert f.kids["Iva"].post(f"/api/learners/{lid}/chats", json={"topic_id": "2026-10-17-erik-english-people", "text": "x"}).status_code == 404


def test_errors_refusals_and_budget(client, fake: FakeProvider):
    f = make_family("fam-err", ["Jan"])
    lid = f.learners["Jan"]
    jan = f.kids["Jan"]
    fake.mode = "busy"
    assert jan.post(f"/api/learners/{lid}/chats", json={"text": "x"}).status_code == 429
    fake.mode = "key"
    assert jan.post(f"/api/learners/{lid}/chats", json={"text": "x"}).status_code == 424
    fake.mode = "refuse"
    out = jan.post(f"/api/learners/{lid}/chats", json={"text": "x"}).json()
    assert "ne morem pomagati" in out["messages"][1]["text"]
    fake.mode = "ok"
    assert jan.post(f"/api/learners/{lid}/chats", json={"text": "x", "images": ["bm90IGFuIGltYWdl"]}).status_code == 400
    assert jan.post(f"/api/learners/{lid}/chats", json={"text": " "}).status_code == 400

    ai = f.admin.get("/api/family/ai").json()
    tutor_job = next(j for j in ai["jobs"] if j["job"] == "tutor_chat")
    assert tutor_job["model"] == "claude-opus-5-5" and tutor_job["per_100_usd"] == pytest.approx(1.0)
    # Cheaper models are offered only after they passed the eval.
    assert f.admin.put("/api/family/ai", json={"routes": [{"job": "tutor_chat", "model": "claude-haiku-5-5"}]}).status_code == 400
    assert f.admin.put("/api/family/ai", json={"routes": [{"job": "tutor_chat", "model": "claude-opus-5-5", "effort": "low"}],
                                               "budget_usd": 0}).json()["budget_usd"] == 0
    r = jan.post(f"/api/learners/{lid}/chats", json={"text": "x"})
    assert r.status_code == 429 and "počiva" in r.json()["detail"]
