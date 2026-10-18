"""Foxy's chats: usage and limits, photos, and turning a chat into an AI request."""
from __future__ import annotations

import base64
import binascii
import hashlib
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..llm import Part, Turn
from ..models import Attachment, LlmCall, TutorChat, TutorMessage
from ..timeutil import iso

MAX_CHAT_MESSAGES = 80  # then a new chat: keeps every request small (and cheap)
MAX_CHAT_IMAGES = 12
MAX_MESSAGE_IMAGES = 4
MAX_IMAGE_BYTES = 3_500_000  # the API takes images up to 5 MB as base64
MEDIA = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

# What the child (or the parent) reads when Foxy can't answer.
TEXT = {
    "sl": {
        "not_configured": "Foxy še ni pripravljen. Prosi starše, da ga vklopijo.",
        "disabled": "Foxy je ta čas izklopljen. Vprašaj starše.",
        "limit": "Za danes je vprašanj dovolj. Jutri bo Foxy spet tu! 🦊",
        "budget": "Foxy ta mesec počiva. Povej staršem.",
        "too_long": "Ta pogovor je že zelo dolg. Začni nov pogovor, pa bo šlo hitreje.",
        "too_many_images": "V tem pogovoru je že veliko slik. Za novo nalogo začni nov pogovor.",
        "busy": "Foxy je trenutno zelo zaposlen. Poskusi znova čez minutko.",
        "unreachable": "Foxyja trenutno ni mogoče doseči. Poskusi znova čez nekaj minut.",
        "key": "Foxy se ne more povezati, ker ključ ne deluje. Povej staršem.",
        "refused": "Pri tem ti ne morem pomagati. Vprašaj starše ali učitelja. Lahko pa nadaljujeva z nalogo! 🦊",
        "empty_reply": "Hmm, tega nisem razumel. Lahko vprašaš še enkrat, malo drugače?",
        "bad_image": "Te slike ne morem odpreti. Poskusi z drugo fotografijo.",
        "empty_message": "Napiši vprašanje ali dodaj fotografijo naloge.",
        "read_only": "Ta pogovor lahko samo bereš.",
    },
    "en": {
        "not_configured": "Foxy isn't set up yet. Ask a parent to switch it on.",
        "disabled": "Foxy is switched off for now. Ask a parent.",
        "limit": "That's enough questions for today. Foxy will be back tomorrow! 🦊",
        "budget": "Foxy is resting for the rest of this month. Tell a parent.",
        "too_long": "This chat is very long now. Start a new chat and it will be quicker.",
        "too_many_images": "This chat has lots of photos already. Start a new chat for a new task.",
        "busy": "Foxy is very busy right now. Try again in a minute.",
        "unreachable": "Foxy can't be reached right now. Try again in a few minutes.",
        "key": "Foxy can't connect because the API key isn't working. Tell a parent.",
        "refused": "I can't help with that one. Ask a parent or a teacher. We can keep going with your task, though! 🦊",
        "empty_reply": "Hmm, I didn't understand that. Could you ask again in a different way?",
        "bad_image": "I can't open this picture. Try another photo.",
        "empty_message": "Write a question or add a photo of your task.",
        "read_only": "You can only read this chat.",
    },
}


def t(lang: str, key: str) -> str:
    return TEXT.get(lang, TEXT["sl"])[key]


# --------------------------------------------------------------------------- #
# Usage, limits and costs
# --------------------------------------------------------------------------- #
def kid_messages_today(db: Session, learner_id: int, day: date) -> int:
    """The daily limit counts the learner's own questions to Foxy (not a parent trying him) and the oral-exam
    answers she checked."""
    from ..models import OralSession, OralTurn

    chat = db.scalar(select(func.count(TutorMessage.id)).join(TutorChat, TutorChat.id == TutorMessage.chat_id)
                     .where(TutorChat.learner_id == learner_id, TutorChat.parent_test.is_(False),
                            TutorMessage.role == "user", TutorMessage.local_date == day)) or 0
    oral = db.scalar(select(func.count(OralTurn.id)).join(OralSession, OralSession.id == OralTurn.session_id)
                     .where(OralSession.learner_id == learner_id, OralTurn.local_date == day)) or 0
    return chat + oral


def month_usage(db: Session, family_id: int, day: date, learner_id: int | None = None) -> dict[str, Any]:
    first = day.replace(day=1)
    q = select(func.count(LlmCall.id), func.coalesce(func.sum(LlmCall.cost_usd), 0.0)).where(
        LlmCall.family_id == family_id, LlmCall.local_date >= first, LlmCall.outcome != "imported")
    if learner_id is not None:
        q = q.where(LlmCall.learner_id == learner_id)
    n, cost = db.execute(q).one()
    return {"month_calls": n, "month_cost_usd": round(float(cost), 4)}


def family_budget_left(db: Session, family_id: int, settings_: dict[str, Any], day: date) -> float | None:
    budget = settings_.get("ai_monthly_budget_usd")
    if budget is None:
        return None
    return float(budget) - month_usage(db, family_id, day)["month_cost_usd"]


# --------------------------------------------------------------------------- #
# Photos
# --------------------------------------------------------------------------- #
def files_dir(family_id: int, learner_id: int) -> Path:
    return settings.files_dir / str(family_id) / str(learner_id)


def decode_image(data: str, lang: str) -> tuple[bytes, str]:
    """A photo sent as base64 (optionally a data: URL) -> (bytes, extension). Raises ValueError with a kid message."""
    if data.startswith("data:"):
        data = data.partition(",")[2]
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(t(lang, "bad_image")) from None
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(t(lang, "bad_image"))
    if raw[:3] == b"\xff\xd8\xff":
        return raw, "jpg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return raw, "png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return raw, "webp"
    raise ValueError(t(lang, "bad_image"))


def save_images(family_id: int, learner_id: int, images: list[tuple[bytes, str]]) -> list[Attachment]:
    folder = files_dir(family_id, learner_id)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for raw, ext in images:
        name = f"{uuid.uuid4().hex}.{ext}"
        (folder / name).write_bytes(raw)
        out.append(Attachment(family_id=family_id, learner_id=learner_id, file_name=name, media_type=MEDIA[ext],
                              bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    return out


def file_url(learner_id: int, name: str) -> str:
    return f"/api/learners/{learner_id}/files/{name}"


# --------------------------------------------------------------------------- #
# Chats
# --------------------------------------------------------------------------- #
def turns(chat: TutorChat | None) -> list[Turn]:
    out: list[Turn] = []
    for m in chat.messages if chat else []:
        parts = []
        for a in m.attachments:
            f = files_dir(chat.family_id, chat.learner_id) / a.file_name
            if f.is_file():
                parts.append(Part(f.read_bytes(), a.media_type))
        out.append(Turn(m.role, m.text, parts))
    return out


def message_out(chat: TutorChat, m: TutorMessage) -> dict[str, Any]:
    return {"id": m.id, "role": m.role, "text": m.text,
            "images": [file_url(chat.learner_id, a.file_name) for a in m.attachments], "created_at": iso(m.created_at)}


def chat_cards(db: Session, chats: list[TutorChat], with_cost: bool) -> list[dict[str, Any]]:
    ids = [c.id for c in chats]
    counts: dict[int, tuple[int, float]] = {}
    if ids:
        rows = db.execute(select(TutorMessage.chat_id, func.count(TutorMessage.id), func.coalesce(func.sum(LlmCall.cost_usd), 0.0))
                          .outerjoin(LlmCall, LlmCall.id == TutorMessage.llm_call_id)
                          .where(TutorMessage.chat_id.in_(ids)).group_by(TutorMessage.chat_id))
        counts = {cid: (n, cost) for cid, n, cost in rows}
    out = []
    for c in chats:
        n, cost = counts.get(c.id, (0, 0.0))
        card = {"id": c.id, "subject": c.subject, "title": c.title, "topic_id": c.topic_id, "task_id": c.task_id,
                "parent_test": c.parent_test, "messages": n, "created_at": iso(c.created_at), "updated_at": iso(c.updated_at)}
        if with_cost:
            card["cost_usd"] = round(float(cost), 4)
        out.append(card)
    return out
