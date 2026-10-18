"""Where routes get content from.

``ContentSource`` hides where topics live. Today they are files checked at start-up
(``FileContentSource``); a database source can come later (in-app generated drafts) without touching
approvals or practice data, which refer to content by string id + version only.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Protocol

from fastapi import HTTPException

from .checker import DATA_DIR, Content, ContentError, load

log = logging.getLogger("ucilnica.content")


class ContentSource(Protocol):
    def content(self) -> Content: ...


class FileContentSource:
    def __init__(self, directory=DATA_DIR) -> None:
        self.directory = directory

    def content(self) -> Content:
        return load(self.directory)


_source: ContentSource = FileContentSource()


def set_source(source: ContentSource) -> None:
    """Tests point this at a scratch folder."""
    global _source
    _source = source
    get_content.cache_clear()


@lru_cache(maxsize=1)
def get_content() -> Content:
    return _source.content()


def content() -> Content:
    """The checked content, or 503 if the files have problems (logged with every problem)."""
    try:
        return get_content()
    except ContentError:
        log.exception("Topics could not be loaded")
        raise HTTPException(503, "Topics can't be loaded right now.") from None


def topic_for_family(slug: str, topic_id: str) -> dict[str, Any]:
    """A topic this family may see (global or its own), else 404."""
    c = content()
    if topic_id not in c.topics or c.scope[topic_id] not in ("global", slug):
        raise HTTPException(404, "Topic not found")
    return c.topics[topic_id]
