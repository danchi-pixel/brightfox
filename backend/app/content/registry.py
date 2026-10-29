"""Where routes get content from.

``ContentSource`` hides where topics live. Today they are files checked at start-up
(``FileContentSource``), then refreshed when files change; a database source can come later without touching
approvals or practice data, which refer to content by string id + version only.
"""
from __future__ import annotations

import logging
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from fastapi import HTTPException

from .checker import DATA_DIR, Content, ContentError, load, topic_folders

log = logging.getLogger("ucilnica.content")


class ContentSource(Protocol):
    def content(self) -> Content: ...


class FileContentSource:
    def __init__(self, directory=DATA_DIR) -> None:
        self.directory = Path(directory)
        self._lock = RLock()
        self._stamp = None
        self._content = None

    def _fingerprint(self) -> tuple:
        # Follow exactly the same folders as the checker, including newly added families/mocks.
        files = [p for _, folder in topic_folders(self.directory)
                 for kind in (folder, folder.parent / "mocks") for p in sorted(kind.glob("*.json"))]
        return tuple((str(p), s.st_mtime_ns, s.st_ctime_ns, s.st_size)
                     for p in files for s in [p.stat()])

    def content(self) -> Content:
        with self._lock:
            stamp = self._fingerprint()
            if self._content is None or stamp != self._stamp:
                # Publish only a complete validated snapshot. A broken edit returns 503, never stale data.
                updated = load(self.directory)
                self._content, self._stamp = updated, stamp
            return self._content


_source: ContentSource = FileContentSource()


def set_source(source: ContentSource) -> None:
    """Tests point this at a scratch folder."""
    global _source
    _source = source


def get_content() -> Content:
    return _source.content()


def content() -> Content:
    """The checked content, or 503 if the files have problems (logged with every problem)."""
    try:
        return get_content()
    except (ContentError, OSError):
        log.exception("Topics could not be loaded")
        raise HTTPException(503, "Topics can't be loaded right now.") from None


def topic_for_family(slug: str, topic_id: str) -> dict[str, Any]:
    """A topic this family may see (global or its own), else 404."""
    c = content()
    if topic_id not in c.topics or c.scope[topic_id] not in ("global", slug):
        raise HTTPException(404, "Topic not found")
    return c.topics[topic_id]
