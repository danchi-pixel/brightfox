"""Choose the model for a job and ask it.

``complete`` never writes to the database (callers read everything first, call, then write: no database
transaction waits on the network). ``record`` adds the cost-ledger row afterwards.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

from sqlalchemy.orm import Session

from ..models import LlmCall, LlmRoute
from . import anthropic_provider
from .base import LLMReply, LLMRequest
from .models import JOBS, MODELS, ModelSpec, approved_models

# Tests swap this for a fake (never the real API in tests).
Provider = Callable[[LLMRequest, ModelSpec, str], LLMReply]
_providers: dict[str, Provider] = {"anthropic": anthropic_provider.complete}
_configured: Callable[[], bool] = anthropic_provider.configured


def set_test_provider(provider: Provider | None, configured: bool = True) -> None:
    global _configured
    if provider is None:
        _providers["anthropic"] = anthropic_provider.complete
        _configured = anthropic_provider.configured
    else:
        _providers["anthropic"] = provider
        _configured = lambda: configured  # noqa: E731


def configured() -> bool:
    return _configured()


def route(db: Session, family_id: int, job: str) -> tuple[ModelSpec, str]:
    """The family's chosen model for a job if it is still allowed, else the default."""
    default = JOBS[job]
    chosen = db.get(LlmRoute, (family_id, job))
    model, effort = default["model"], default["effort"]
    if chosen is not None and chosen.model in approved_models(job):
        model = chosen.model
        effort = chosen.effort or effort
    spec = MODELS[model]
    return spec, effort if effort in spec.efforts else default["effort"]


def complete(req: LLMRequest, spec: ModelSpec, effort: str) -> LLMReply:
    return _providers[spec.provider](req, spec, effort)


def record(db: Session, *, family_id: int, learner_id: int | None, job: str, reply: LLMReply, day: date) -> LlmCall:
    outcome = "refused" if reply.refused else "cut_off" if reply.cut_off else "ok"
    call = LlmCall(family_id=family_id, learner_id=learner_id, job=job, provider=reply.provider, model=reply.model,
                   input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
                   cache_read_tokens=reply.cache_read_tokens, cache_write_tokens=reply.cache_write_tokens,
                   cost_usd=round(reply.cost_usd, 6), latency_ms=reply.latency_ms, outcome=outcome, local_date=day)
    db.add(call)
    return call
