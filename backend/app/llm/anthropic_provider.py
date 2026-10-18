"""Claude through the Anthropic API.

* Thinking is always on for these models; ``effort`` is the only control and is always sent explicitly
  (the defaults differ per model).
* ``fallbacks: "default"`` (beta ``server-side-fallback-2026-07-01``) re-runs a request a safety classifier
  declined by mistake on another model, for models that support it (not Haiku 5.5).
* Prompt caching: automatic caching of everything up to the newest message, plus a breakpoint after each
  system block marked ``cache`` (the fixed rules, a topic's notes).
* Only text is replayed from earlier assistant turns (no thinking blocks), so switching model mid-chat is
  safe.
"""
from __future__ import annotations

import base64
import os
import time
from functools import lru_cache
from typing import Any

from .base import (LLMAuthError, LLMBadRequest, LLMRateLimited, LLMReply, LLMRequest, LLMUnavailable, Turn)
from .models import ModelSpec, cost_usd

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def build_messages(turns: list[Turn]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in turns:
        if t.role == "assistant":
            out.append({"role": "assistant", "content": t.text or "…"})
            continue
        content: list[dict[str, Any]] = [
            {"type": "image", "source": {"type": "base64", "media_type": p.media_type,
                                         "data": base64.standard_b64encode(p.data).decode("ascii")}}
            for p in t.images
        ]
        content.append({"type": "text", "text": t.text.strip() or "(A photo of my task.)"})
        out.append({"role": "user", "content": content})
    return out


@lru_cache(maxsize=1)
def _client():
    import anthropic

    return anthropic.Anthropic(timeout=120.0, max_retries=2)


def complete(req: LLMRequest, spec: ModelSpec, effort: str) -> LLMReply:
    import anthropic

    system = []
    for b in req.system:
        block: dict[str, Any] = {"type": "text", "text": b.text}
        if b.cache:
            block["cache_control"] = {"type": "ephemeral"}
        system.append(block)
    kwargs: dict[str, Any] = {
        "model": spec.id,
        "max_tokens": req.max_tokens,
        "system": system,
        "messages": build_messages(req.turns),
        "output_config": {"effort": effort},
        "cache_control": {"type": "ephemeral"},
    }
    if spec.server_fallback:
        kwargs["betas"] = [FALLBACK_BETA]
        kwargs["fallbacks"] = "default"
    started = time.monotonic()
    try:
        response = _client().beta.messages.create(**kwargs)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        raise LLMAuthError(str(exc)) from exc
    except anthropic.RateLimitError as exc:
        raise LLMRateLimited(str(exc)) from exc
    except anthropic.APIConnectionError as exc:
        raise LLMUnavailable(str(exc)) from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code in (429, 529) or exc.status_code >= 500:
            raise LLMRateLimited(str(exc)) from exc
        raise LLMBadRequest(str(exc)) from exc
    refused = response.stop_reason == "refusal"
    text = "" if refused else "\n\n".join(
        b.text for b in response.content if getattr(b, "type", None) == "text" and b.text).strip()
    u = response.usage
    model = response.model or spec.id
    tokens = (u.input_tokens or 0, u.output_tokens or 0, getattr(u, "cache_read_input_tokens", None) or 0,
              getattr(u, "cache_creation_input_tokens", None) or 0)
    return LLMReply(text=text, model=model, provider="anthropic", refused=refused,
                    cut_off=response.stop_reason == "max_tokens", input_tokens=tokens[0], output_tokens=tokens[1],
                    cache_read_tokens=tokens[2], cache_write_tokens=tokens[3], cost_usd=cost_usd(model, *tokens),
                    latency_ms=int((time.monotonic() - started) * 1000))
