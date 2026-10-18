"""The AI layer: one provider-neutral way to ask a model, model choice per job, prices and the cost ledger.

Routers never import a provider SDK; they call ``llm.complete`` and catch the neutral errors in ``base``.
"""
from .base import (LLMAuthError, LLMBadRequest, LLMError, LLMRateLimited, LLMReply, LLMRequest, LLMUnavailable, Part,
                   SystemBlock, Turn)
from .service import complete, configured

__all__ = ["LLMAuthError", "LLMBadRequest", "LLMError", "LLMRateLimited", "LLMReply", "LLMRequest", "LLMUnavailable",
           "Part", "SystemBlock", "Turn", "complete", "configured"]
