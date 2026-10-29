"""Health check (public: the container healthcheck and the smoke test use it)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..access import public
from ..config import APP_NAME, APP_VERSION, WORKSPACE_ID, settings

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(_=Depends(public)) -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME, "version": APP_VERSION,
            "workspace_id": WORKSPACE_ID, "mode": "local" if settings.local_family else "standard"}
