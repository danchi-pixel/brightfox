# syntax=docker/dockerfile:1
# Učilnica - one image with the API and the built web app.
# Built on the server by deploy/server/update.sh from the source deploy.ps1 uploads (build context: that
# source, see compose.yaml). The data folder (/data) is a volume and never part of the image.

# ---------------------------------------------------------------- web app (build only)
FROM node:22.23.3-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
# frontend/.env carries VITE_APP_NAME (the page title).
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM python:3.12.15-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tini (proper signal handling), curl (health check)
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt ./
# SQLAlchemy's compiled speed-ups stay: deleting *_cy.pyd is only for Smart App Control on the Windows PC.
RUN pip install -r requirements.txt \
 && python -c "import sqlalchemy, alembic, fastapi, anthropic; print('sqlalchemy', sqlalchemy.__version__)"

COPY backend/ ./
COPY --from=web /web/dist /app/web
# The app runs as an unprivileged user: make the code readable regardless of the
# permissions the files had on the build host (owned by root, so still not writable).
RUN chmod -R a+rX /app

# Production settings: secure cookies, behind PitchDriven's Caddy, data in /data.
ENV UCILNICA_DATA_DIR=/data \
    UCILNICA_STATIC_DIR=/app/web \
    UCILNICA_API_HOST=0.0.0.0 \
    UCILNICA_API_PORT=8000 \
    UCILNICA_COOKIE_SECURE=1 \
    UCILNICA_BEHIND_PROXY=1 \
    HOME=/tmp

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1
ENTRYPOINT ["tini", "--"]
CMD ["python", "run.py"]
