"""One visibility policy for topics and mocks; local authoring is explicitly opt-in.

The file's `for` field is the assignment. It never grants access across families, to archived
learners, or on production. Existing approvals still work; no progress or approval rows are rewritten.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import LearnerCtx
from ..config import settings
from ..models import ContentAccess
from .checker import Content


def locally_assigned(item: dict, slug: str, name: str, archived: bool = False) -> bool:
    return bool(settings.local_family == slug and not archived
                and name.strip().casefold() in {n.strip().casefold() for n in item.get("for", [])})


def visible_ids(db: Session, c: Content, ctx: LearnerCtx, kind: str) -> list[str]:
    rows = db.scalars(select(ContentAccess).where(ContentAccess.kind == kind,
        ContentAccess.family_id == ctx.family_id, ContentAccess.learner_id == ctx.learner.id))
    approved = {a.content_id: a.version for a in rows}
    items = c.topics if kind == "topic" else c.mocks
    ids = c.for_family(ctx.family.slug) if kind == "topic" else c.mocks_for_family(ctx.family.slug)
    return [i for i in ids if approved.get(i) == items[i]["version"]
            or locally_assigned(items[i], ctx.family.slug, ctx.learner.name, ctx.learner.archived)]
