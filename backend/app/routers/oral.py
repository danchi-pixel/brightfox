"""The oral exam in a learner's space: start a session for a topic, answer its questions one by one (Foxy
checks each answer), and read past sessions. Each checked answer counts as one Foxy question for the day."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import llm
from ..access import LearnerCtx, learner_in_scope
from ..db import get_db
from ..llm import service as llm_service
from ..models import OralSession, OralTurn
from ..oral import grading
from ..timeutil import iso, local_today
from ..tutor import service as tutor
from .learner import viewer_lang, visible_topic

log = logging.getLogger("ucilnica.oral")
router = APIRouter(prefix="/api/learners/{lid}/oral", tags=["oral"])

MAX_QUESTIONS = 5


def _questions(topic: dict[str, Any]) -> list[dict[str, Any]]:
    return topic.get("oral", [])[:MAX_QUESTIONS]


def _session_out(s: OralSession, topic: dict[str, Any] | None) -> dict[str, Any]:
    qs = {q["id"]: q for q in (topic or {}).get("oral", [])}
    return {"id": s.id, "topic_id": s.topic_id, "topic_title": (topic or {}).get("title"), "date": iso(s.local_date),
            "questions": [{"id": q["id"], "question": q["question"]} for q in _questions(topic or {})],
            "turns": [{"question_id": t.question_id, "question": t.question_text, "answer": t.answer_text, "verdict": t.verdict,
                       "feedback": t.feedback, "model_answer": qs.get(t.question_id, {}).get("model_answer")} for t in s.turns]}


class StartIn(BaseModel):
    topic_id: str = Field(max_length=80)
    today: str | None = None


@router.post("", status_code=201)
def start(body: StartIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_self()
    topic = visible_topic(db, ctx, body.topic_id)
    if not topic.get("oral"):
        raise HTTPException(404, "This topic has no oral exam.")
    s = OralSession(family_id=ctx.family_id, learner_id=ctx.learner.id, topic_id=body.topic_id, version=topic["version"],
                    local_date=local_today(ctx.family.timezone, body.today))
    db.add(s)
    db.commit()
    return _session_out(s, topic)


@router.get("")
def sessions(db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> list[dict[str, Any]]:
    from ..content.registry import content

    c = content()
    rows = db.scalars(select(OralSession).where(OralSession.learner_id == ctx.learner.id).order_by(OralSession.id.desc()).limit(30))
    return [_session_out(s, c.topics.get(s.topic_id)) for s in rows if s.turns]


def _own(db: Session, ctx: LearnerCtx, sid: int) -> OralSession:
    s = db.get(OralSession, sid)
    if s is None or s.learner_id != ctx.learner.id:
        raise HTTPException(404, "Not found")
    return s


@router.get("/{sid}")
def get_session(sid: int, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    s = _own(db, ctx, sid)
    from ..content.registry import content

    return _session_out(s, content().topics.get(s.topic_id))


class AnswerIn(BaseModel):
    question_id: str = Field(max_length=40)
    answer: str = Field(min_length=1, max_length=1500)
    today: str | None = None


@router.post("/{sid}/answers")
def answer(sid: int, body: AnswerIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_self()
    s = _own(db, ctx, sid)
    topic = visible_topic(db, ctx, s.topic_id)
    q = next((x for x in _questions(topic) if x["id"] == body.question_id), None)
    if q is None:
        raise HTTPException(400, "Unknown question.")
    lang = viewer_lang(db, ctx)
    lr = ctx.learner
    day = local_today(ctx.family.timezone, body.today)
    if not llm.configured():
        raise HTTPException(409, tutor.t(lang, "not_configured"))
    if not lr.tutor_enabled:
        raise HTTPException(409, tutor.t(lang, "disabled"))
    if tutor.kid_messages_today(db, lr.id, day) >= lr.tutor_daily_limit:
        raise HTTPException(429, tutor.t(lang, "limit"))
    left = tutor.family_budget_left(db, ctx.family_id, ctx.family.settings or {}, day)
    if left is not None and left <= 0:
        raise HTTPException(429, tutor.t(lang, "budget"))
    req = grading.request(question=q, answer=body.answer.strip(), grade=lr.grade, language=lr.language or "sl",
                          topic_title=topic["title"])
    spec, effort = llm_service.route(db, ctx.family_id, "oral_grading")
    db.rollback()  # no transaction waits on the network
    try:
        reply = llm_service.complete(req, spec, effort)
    except llm.LLMAuthError:
        raise HTTPException(424, tutor.t(lang, "key")) from None
    except llm.LLMRateLimited:
        raise HTTPException(429, tutor.t(lang, "busy")) from None
    except (llm.LLMUnavailable, llm.LLMBadRequest):
        log.warning("Oral grading failed", exc_info=True)
        raise HTTPException(424, tutor.t(lang, "unreachable")) from None
    verdict, feedback = ("partly", tutor.t(lang, "refused")) if reply.refused else grading.parse(reply.text)
    s = _own(db, ctx, sid)
    call = llm_service.record(db, family_id=ctx.family_id, learner_id=lr.id, job="oral_grading", reply=reply, day=day)
    db.flush()
    s.turns.append(OralTurn(family_id=ctx.family_id, question_id=q["id"], question_text=q["question"],
                            answer_text=body.answer.strip(), verdict=verdict, feedback=feedback, llm_call_id=call.id, local_date=day))
    db.commit()
    return {"verdict": verdict, "feedback": feedback, "model_answer": q["model_answer"],
            "left_today": max(0, lr.tutor_daily_limit - tutor.kid_messages_today(db, lr.id, day))}
