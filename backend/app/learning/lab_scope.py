"""One fail-closed source policy for lab practice and the older classroom paths.

Content and progress are never rewritten. Mixed/missing provenance needs review;
parent activation applies only to unambiguously textbook questions in that lesson.
"""
from sqlalchemy import select
from ..models import LabActivation


def source_group(bank, source_ids):
    sources = {s["id"]: s.get("group", "review") for s in bank["sources"]}
    groups = {sources.get(s, "review") for s in source_ids}
    return next(iter(groups)) if len(groups) == 1 else "review"


def availability(db, ctx, topic):
    bank = topic["lab"]
    enabled = set(db.scalars(select(LabActivation.lesson_id).where(
        LabActivation.family_id == ctx.family_id, LabActivation.learner_id == ctx.learner.id,
        LabActivation.topic_id == topic["id"], LabActivation.enabled.is_(True))))
    groups = {q["id"]: source_group(bank, q["sources"]) for q in bank["questions"]}
    active = [q["id"] for q in bank["questions"] if groups[q["id"]] == "notebook"
              or groups[q["id"]] == "textbook" and q["topic"] in enabled]
    return {"enabled_lessons": sorted(enabled), "active_questions": active,
            "question_groups": groups, "can_manage": ctx.user.is_admin}


def practice_topic(db, ctx, topic):
    """Filter legacy tasks/cards for direct links, readiness, plans and mistake review.

Keep the full lab for read-only browsing, with practice permission checked separately.
Unmapped legacy items are held back rather than assigned by text guessing at runtime.
"""
    if not topic.get("lab"):
        return topic
    bank = topic["lab"]
    active = set(availability(db, ctx, topic)["active_questions"])
    links = bank.get("legacy", {})
    tasks = links.get("tasks", {})
    cards = links.get("cards", {})
    sections = links.get("sections", {})
    lessons = {l["id"] for l in bank["lessons"] if all(
        q["id"] in active for q in bank["questions"] if q["topic"] == l["id"])}
    study = topic.get("study", {})
    return {**topic, "tasks": [t for t in topic["tasks"] if tasks.get(t["id"]) in active],
            "challenge": [t for t in topic.get("challenge", []) if tasks.get(t["id"]) in active],
            "oral": [q for q in topic.get("oral", []) if q["id"] in active],
            "study": {**study,
                "sections": [s for s in study.get("sections", []) if sections.get(s["title"]) in lessons],
                "cards": [c for c in study.get("cards", []) if cards.get(c["back"]) in active]}}
