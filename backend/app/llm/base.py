"""Provider-neutral request and reply types, and the errors routers turn into messages for the kids."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Part:
    """One image in a user turn (text goes in ``Turn.text``)."""

    data: bytes
    media_type: str  # image/jpeg | image/png | image/webp


@dataclass
class Turn:
    role: str  # user | assistant
    text: str
    images: list[Part] = field(default_factory=list)


@dataclass
class SystemBlock:
    text: str
    cache: bool = False  # a cache breakpoint after this block (fixed rules, a topic's notes)


@dataclass
class LLMRequest:
    job: str  # tutor_chat | oral_grading | open_feedback
    system: list[SystemBlock]
    turns: list[Turn]
    max_tokens: int = 8000  # includes thinking; replies themselves are short


@dataclass
class LLMReply:
    text: str
    model: str
    provider: str
    refused: bool
    cut_off: bool
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class LLMError(Exception):
    """Base for the neutral errors below."""


class LLMAuthError(LLMError):
    """The key was refused."""


class LLMRateLimited(LLMError):
    """Too many requests, or the provider is overloaded: try again in a minute."""


class LLMUnavailable(LLMError):
    """The provider can't be reached (network, outage)."""


class LLMBadRequest(LLMError):
    """The provider refused the request itself (a bug on our side, logged)."""
