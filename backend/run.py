"""Start the Učilnica API server (used by start.bat and the Docker image)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

if "--local" in sys.argv:
    os.environ.setdefault("UCILNICA_LOCAL_FAMILY", "danijel")

from app.config import settings  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=os.environ.get("UCILNICA_LOG_LEVEL", "info"),
        # Behind the reverse proxy the client address comes from X-Forwarded-For;
        # the app container is only reachable from the proxy.
        proxy_headers=settings.behind_proxy,
        forwarded_allow_ips="*" if settings.behind_proxy else None,
        server_header=False,
        reload="--local" in sys.argv,
        reload_dirs=[str(Path(__file__).resolve().parent / "app")] if "--local" in sys.argv else None,
    )
