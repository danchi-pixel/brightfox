"""The models a family can choose from, the AI jobs, and prices.

Prices are USD per million tokens (input, output, cache read, 5-minute cache write), from Anthropic's
pricing page (October 2026). They are only for the parents' cost figures; the bill comes from Anthropic.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("ucilnica.llm")


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str
    label: str
    tier: str  # shown to parents: "best", "balanced", "cheapest"
    server_fallback: bool  # supports fallbacks: "default" (re-run a mistaken refusal on another model)
    efforts: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")


MODELS: dict[str, ModelSpec] = {m.id: m for m in (
    ModelSpec("claude-opus-5-5", "anthropic", "Claude Opus 5.5", "best", True),
    ModelSpec("claude-sonnet-5-5", "anthropic", "Claude Sonnet 5.5", "balanced", True),
    ModelSpec("claude-haiku-5-5", "anthropic", "Claude Haiku 5.5", "cheapest", False),
)}

# What each AI job is for, and its default (today's behaviour: Opus 5.5 at medium effort).
JOBS: dict[str, dict[str, str]] = {
    "tutor_chat": {"label": "Foxy (homework chat)", "model": "claude-opus-5-5", "effort": "medium"},
    "oral_grading": {"label": "Oral exam checking", "model": "claude-opus-5-5", "effort": "medium"},
    "open_feedback": {"label": "Feedback on written answers", "model": "claude-opus-5-5", "effort": "medium"},
}

_PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    # Models a server-side fallback may answer with:
    "claude-opus-5": (5.0, 25.0, 0.50, 6.25),
    "claude-opus-4-8": (5.0, 25.0, 0.50, 6.25),
}
_HAIKU_LONG = (0.50, 2.50, 0.05, 0.625)  # Haiku 5.5 prompts over 100K tokens


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int, cache_write: int) -> float:
    prompt = input_tokens + cache_read + cache_write
    if model == "claude-haiku-5-5" and prompt > 100_000:
        prices = _HAIKU_LONG
    elif model in _PRICES:
        prices = _PRICES[model]
    else:
        # Unknown (e.g. a new fallback model): count it at the dearest known price, never too low.
        log.warning("No price for model %s; using the highest known price", model)
        prices = max(_PRICES.values(), key=lambda p: p[1])
    p_in, p_out, p_read, p_write = prices
    return (input_tokens * p_in + output_tokens * p_out + cache_read * p_read + cache_write * p_write) / 1_000_000


APPROVED_FILE = Path(__file__).parent / "approved_models.json"


def approved_models(job: str) -> list[str]:
    """Models a parent may pick for a job: the default always, others only after they passed the eval
    (``backend/evals``), recorded in approved_models.json as {"<job>": ["<model>", ...]}."""
    allowed = [JOBS[job]["model"]]
    try:
        data = json.loads(APPROVED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    for m in data.get(job, []):
        if m in MODELS and m not in allowed:
            allowed.append(m)
    return allowed
