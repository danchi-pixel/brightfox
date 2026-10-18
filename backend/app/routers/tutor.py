"""Foxy: the learner's chats with the homework tutor.

Parents read every chat (the kids are told); a parent may also try Foxy in a learner's space (marked as a
test, hidden from the kid, not counted against the daily limit). A chat can start from a topic or one of its
tasks ("Vprašaj Foxyja"); Foxy then gets that topic's notes and terms, so he explains it the school's way.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import llm
from ..access import LearnerCtx, learner_in_scope
from ..db import get_db
from ..llm import service as llm_service
from ..models import Attachment, TutorChat, TutorMessage
from ..timeutil import local_today
from ..tutor import prompts
from ..tutor import service as tutor
from .learner import viewer_lang, visible_topic

log = logging.getLogger("ucilnica.tutor")
router = APIRouter(prefix="/api/learners/{lid}", tags=["tutor"])

FileName = Annotated[str, Path(pattern=r"^[a-f0-9]{32}\.(jpg|png|webp)$")]


def _visible(ctx: LearnerCtx):
    """Parents see every chat (their own tests marked); the learner sees their own chats only."""
    q = select(TutorChat).where(TutorChat.learner_id == ctx.learner.id)
    return q if not ctx.is_self else q.where(TutorChat.parent_test.is_(False))


def _can_send(ctx: LearnerCtx, chat: TutorChat | None) -> bool:
    if chat is not None and chat.parent_test:
        return ctx.user.is_admin
    return ctx.is_self or (ctx.user.is_admin and chat is None)


def _chat_out(db: Session, ctx: LearnerCtx, chat: TutorChat) -> dict[str, Any]:
    return {"chat": tutor.chat_cards(db, [chat], with_cost=ctx.user.is_admin)[0],
            "messages": [tutor.message_out(chat, m) for m in chat.messages],
            "can_send": _can_send(ctx, chat)}


class MessageIn(BaseModel):
    text: str = Field(default="", max_length=2000)
    images: list[Annotated[str, Field(max_length=5_000_000)]] = Field(default_factory=list,
                                                                       max_length=tutor.MAX_MESSAGE_IMAGES)
    today: str | None = None


class NewChatIn(MessageIn):
    subject: str = "other"
    topic_id: str | None = Field(default=None, max_length=80)
    task_id: str | None = Field(default=None, max_length=40)


def _exchange(db: Session, ctx: LearnerCtx, chat: TutorChat | None, body: MessageIn, *, subject: str,
              topic_id: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    """The learner's message -> Foxy's reply; both are saved only when Foxy answered.

    Everything is read before the AI call and written after it, so no database write waits on the network."""
    lang = viewer_lang(db, ctx)
    lr = ctx.learner
    if not _can_send(ctx, chat):
        raise HTTPException(403, tutor.t(lang, "read_only"))
    text = body.text.strip()
    if not text and not body.images:
        raise HTTPException(400, tutor.t(lang, "empty_message"))
    if not llm.configured():
        raise HTTPException(409, tutor.t(lang, "not_configured"))
    test = chat.parent_test if chat is not None else not ctx.is_self
    day = local_today(ctx.family.timezone, body.today)
    if not test:
        if not lr.tutor_enabled:
            raise HTTPException(409, tutor.t(lang, "disabled"))
        if tutor.kid_messages_today(db, lr.id, day) >= lr.tutor_daily_limit:
            raise HTTPException(429, tutor.t(lang, "limit"))
    left = tutor.family_budget_left(db, ctx.family_id, ctx.family.settings or {}, day)
    if left is not None and left <= 0:
        raise HTTPException(429, tutor.t(lang, "budget"))
    if chat is not None:
        if len(chat.messages) >= tutor.MAX_CHAT_MESSAGES:
            raise HTTPException(409, tutor.t(lang, "too_long"))
        sent = sum(len(m.attachments) for m in chat.messages)
        if body.images and sent + len(body.images) > tutor.MAX_CHAT_IMAGES:
            raise HTTPException(409, tutor.t(lang, "too_many_images"))
    try:
        images = [tutor.decode_image(i, lang) for i in body.images]
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None

    topic_id = chat.topic_id if chat is not None else topic_id
    task_id = chat.task_id if chat is not None else task_id
    system = [llm.SystemBlock(prompts.RULES, cache=True)]
    if topic_id:
        system.append(llm.SystemBlock(prompts.topic_block(visible_topic(db, ctx, topic_id), task_id), cache=True))
    system.append(llm.SystemBlock(prompts.learner_context(
        name=lr.name, grade=lr.grade, language=lr.language or "sl", subject=chat.subject if chat else subject,
        interests=lr.interests, notes=lr.tutor_notes)))
    new_turn = llm.Turn("user", text, [llm.Part(raw, tutor.MEDIA[ext]) for raw, ext in images])
    spec, effort = llm_service.route(db, ctx.family_id, "tutor_chat")
    request = llm.LLMRequest(job="tutor_chat", system=system, turns=tutor.turns(chat) + [new_turn])
    db.rollback()  # end the read transaction before waiting on the network
    try:
        reply = llm_service.complete(request, spec, effort)
    except llm.LLMAuthError:
        log.error("The AI provider refused the API key")
        raise HTTPException(424, tutor.t(lang, "key")) from None
    except llm.LLMRateLimited:
        raise HTTPException(429, tutor.t(lang, "busy")) from None
    except llm.LLMUnavailable:
        log.warning("The AI provider could not be reached")
        raise HTTPException(424, tutor.t(lang, "unreachable")) from None
    except llm.LLMBadRequest:
        log.exception("The AI provider refused the request")
        raise HTTPException(424, tutor.t(lang, "unreachable")) from None

    answer = tutor.t(lang, "refused") if reply.refused else (reply.text or tutor.t(lang, "empty_reply"))
    if reply.cut_off:
        answer += " …"
    if chat is None:
        chat = TutorChat(family_id=ctx.family_id, learner_id=lr.id, subject=subject, topic_id=topic_id, task_id=task_id,
                         parent_test=test, title="")
        db.add(chat)
    if not chat.title:
        chat.title = (text[:60] + ("…" if len(text) > 60 else "")) if text else "📷"
    chat.updated_at = datetime.now(timezone.utc)
    call = llm_service.record(db, family_id=ctx.family_id, learner_id=lr.id, job="tutor_chat", reply=reply, day=day)
    db.flush()  # the ledger row's id, for the reply
    asked = TutorMessage(family_id=ctx.family_id, role="user", text=text, local_date=day)
    asked.attachments.extend(tutor.save_images(ctx.family_id, lr.id, images))
    answered = TutorMessage(family_id=ctx.family_id, role="assistant", text=answer, local_date=day, llm_call_id=call.id)
    chat.messages.extend([asked, answered])
    db.commit()
    db.refresh(chat)
    return {**_chat_out(db, ctx, chat), "left_today": max(0, lr.tutor_daily_limit - tutor.kid_messages_today(db, lr.id, day))}


@router.get("/chats")
def list_chats(db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> list[dict[str, Any]]:
    chats = list(db.scalars(_visible(ctx).order_by(TutorChat.updated_at.desc(), TutorChat.id.desc())))
    return tutor.chat_cards(db, chats, with_cost=ctx.user.is_admin)


@router.post("/chats", status_code=201)
def new_chat(body: NewChatIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    """Start a chat with its first message (so there are never empty chats)."""
    subject = body.subject
    if body.topic_id:
        topic = visible_topic(db, ctx, body.topic_id)
        subject = topic["subject"]
        if body.task_id and body.task_id not in {x["id"] for x in topic["tasks"] + topic.get("challenge", [])}:
            raise HTTPException(400, "Unknown task.")
    elif body.task_id:
        raise HTTPException(400, "A task needs its topic.")
    if subject not in prompts.SUBJECTS:
        raise HTTPException(400, "Unknown subject.")
    return _exchange(db, ctx, None, body, subject=subject, topic_id=body.topic_id, task_id=body.task_id)


def _chat(db: Session, ctx: LearnerCtx, cid: int) -> TutorChat:
    chat = db.scalars(_visible(ctx).where(TutorChat.id == cid)).first()
    if chat is None:
        raise HTTPException(404, "Chat not found")
    return chat


@router.get("/chats/{cid}")
def get_chat(cid: int, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    return _chat_out(db, ctx, _chat(db, ctx, cid))


@router.post("/chats/{cid}/messages")
def send_message(cid: int, body: MessageIn, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    chat = _chat(db, ctx, cid)
    return _exchange(db, ctx, chat, body, subject=chat.subject)


@router.delete("/chats/{cid}")
def delete_chat(cid: int, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> dict[str, Any]:
    ctx.require_admin()
    chat = _chat(db, ctx, cid)
    names = [a.file_name for m in chat.messages for a in m.attachments]
    db.delete(chat)
    db.commit()
    for name in names:
        (tutor.files_dir(ctx.family_id, ctx.learner.id) / name).unlink(missing_ok=True)
    return {"deleted": cid}


@router.get("/files/{name}")
def chat_file(name: FileName, db: Session = Depends(get_db), ctx: LearnerCtx = Depends(learner_in_scope)) -> FileResponse:
    # Only photos from chats this viewer may open (a learner never sees a parent's test photos).
    visible = _visible(ctx).with_only_columns(TutorChat.id)
    a = db.scalars(select(Attachment).join(TutorMessage, TutorMessage.id == Attachment.message_id)
                   .where(Attachment.file_name == name, Attachment.learner_id == ctx.learner.id,
                          TutorMessage.chat_id.in_(visible))).first()
    f = tutor.files_dir(ctx.family_id, ctx.learner.id) / name
    if a is None or not f.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(f, media_type=a.media_type, headers={"Cache-Control": "private, max-age=86400"})
