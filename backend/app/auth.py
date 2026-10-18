"""Sign-in.

* Passwords are hashed with scrypt (memory-hard, Python standard library).
* A successful login creates a server-side session; the browser gets a random token in an HttpOnly,
  SameSite=Strict cookie (Secure on HTTPS). Only a SHA-256 of the token is stored.
* Every ``/api`` request except health and the sign-in endpoints needs a valid session (401 otherwise).
  Sign-in is always on, also locally (a scratch family for development): there is no "everyone is an
  admin" mode.
* Failed logins are rate-limited per client address and per username.
* An account belongs to one family. ``admin`` (a parent) may do everything in that family; ``learner``
  (a kid) only the self-service sign-in endpoints and their own ``/api/learners/<own id>/...`` space.
  This middleware is the coarse fence; the routers check every object again (``app/access.py``).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import settings
from .db import SessionLocal
from .models import AuthSession, Family, Learner, User

COOKIE_NAME = "uc_session"
MIN_PASSWORD_LENGTH = 10

_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024

PUBLIC_PATHS = {"/api/health", "/api/auth/status", "/api/auth/login", "/api/auth/logout"}
PROTECTED_PREFIXES = ("/api/", "/docs", "/redoc", "/openapi.json")

ROLES = ("admin", "learner")

# What a learner may call besides their own /api/learners/<id>/... space.
_LEARNER_SELF_SERVICE: list[tuple[set[str], re.Pattern[str]]] = [
    ({"GET"}, re.compile(r"/api/auth/status")),
    ({"POST"}, re.compile(r"/api/auth/(change-password|logout-everywhere)")),
    ({"PUT"}, re.compile(r"/api/auth/preferences")),
]
_LEARNER_SPACE = re.compile(r"/api/learners/(\d+)(/.*)?")


@dataclass(frozen=True)
class Identity:
    """The signed-in account behind a request."""

    id: int
    family_id: int
    username: str
    role: str
    learner_id: int | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def learner_may_call(identity: Identity, method: str, path: str) -> bool:
    if any(method in methods and pattern.fullmatch(path) for methods, pattern in _LEARNER_SELF_SERVICE):
        return True
    m = _LEARNER_SPACE.fullmatch(path)
    return m is not None and identity.learner_id is not None and int(m.group(1)) == identity.learner_id


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
                        maxmem=_SCRYPT_MAXMEM, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        dk = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p),
                            maxmem=_SCRYPT_MAXMEM, dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)


# A real hash, used to spend the same time when the username doesn't exist.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def check_password_strength(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > 256:
        return "That password is too long."
    if password.strip() != password:
        return "The password can't start or end with a space."
    return None


USERNAME_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}")


def clean_username(username: str) -> str:
    username = username.strip().lower()
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("Use letters, numbers, dots, dashes or underscores for the username.")
    return username


def find_user(db: Session, username: str) -> User | None:
    return db.scalars(select(User).where(User.username == username.strip().lower())).first()


def create_account(db: Session, family_id: int, username: str, password: str, *, role: str,
                   learner_id: int | None = None) -> User:
    """A new account in a family. A learner account belongs to one learner of that family (at most one
    account per learner)."""
    problem = check_password_strength(password)
    if problem:
        raise ValueError(problem)
    username = clean_username(username)
    if find_user(db, username) is not None:
        raise ValueError("That username is already taken.")
    _check_role(db, family_id, role, learner_id)
    user = User(family_id=family_id, username=username, password_hash=hash_password(password), role=role,
                learner_id=learner_id if role == "learner" else None)
    db.add(user)
    db.commit()
    _cache.clear()
    return user


def _check_role(db: Session, family_id: int, role: str, learner_id: int | None, user_id: int | None = None) -> None:
    if role not in ROLES:
        raise ValueError(f"Role must be one of: {', '.join(ROLES)}.")
    if role == "learner":
        learner = db.get(Learner, learner_id) if learner_id is not None else None
        if learner is None or learner.family_id != family_id:
            raise ValueError("A learner account must belong to one of this family's learners.")
        taken = db.scalars(select(User.id).where(User.learner_id == learner_id)).first()
        if taken is not None and taken != user_id:
            raise ValueError("This learner already has an account.")
    elif learner_id is not None:
        raise ValueError("A parent account isn't linked to a learner.")


def set_password(db: Session, user: User, password: str) -> None:
    """Change the password and sign that account out everywhere."""
    problem = check_password_strength(password)
    if problem:
        raise ValueError(problem)
    user.password_hash = hash_password(password)
    user.password_changed_at = datetime.now(timezone.utc)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    _cache.clear()


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = find_user(db, username)
    if user is None:
        verify_password(password, _DUMMY_HASH)  # same work either way: no username probing by timing
        return None
    return user if verify_password(password, user.password_hash) else None


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def create_session(db: Session, user: User, user_agent: str | None) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=settings.session_days)
    db.add(AuthSession(user_id=user.id, token_hash=_token_hash(token), created_at=now, expires_at=expires,
                       last_seen_at=now, user_agent=(user_agent or "")[:300] or None))
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now))  # tidy up old sessions
    db.commit()
    return token, expires


def end_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
        db.commit()
        _cache.pop(_token_hash(token), None)


def end_all_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    db.commit()
    _cache.clear()


class _SessionCache:
    """Short-lived cache so a page's burst of requests doesn't hit the database every time."""

    TTL = 30.0

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Identity]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Identity | None:
        with self._lock:
            hit = self._data.get(key)
            if hit and time.monotonic() - hit[0] < self.TTL:
                return hit[1]
            self._data.pop(key, None)
            return None

    def put(self, key: str, identity: Identity) -> None:
        with self._lock:
            if len(self._data) > 2000:
                self._data.clear()
            self._data[key] = (time.monotonic(), identity)

    def pop(self, key: str, default=None):
        with self._lock:
            return self._data.pop(key, default)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = _SessionCache()


def session_user(token: str | None) -> Identity | None:
    """The account behind a valid session token, else None (also None while the family is suspended)."""
    if not token or len(token) > 200:
        return None
    key = _token_hash(token)
    cached = _cache.get(key)
    if cached:
        return cached
    with SessionLocal() as db:
        row = db.execute(select(AuthSession, User, Family.status)
                         .join(User, User.id == AuthSession.user_id)
                         .join(Family, Family.id == User.family_id)
                         .where(AuthSession.token_hash == key)).first()
        if row is None:
            return None
        sess, user, status = row
        now = datetime.now(timezone.utc)
        if _aware(sess.expires_at) <= now:
            db.delete(sess)
            db.commit()
            return None
        if status != "active":
            return None
        if now - _aware(sess.last_seen_at) > timedelta(minutes=10):
            sess.last_seen_at = now
            db.commit()
        identity = Identity(user.id, user.family_id, user.username, user.role, user.learner_id)
        _cache.put(key, identity)
        return identity


def cookie_value(scope_or_headers) -> str | None:
    headers = scope_or_headers.get("headers", []) if isinstance(scope_or_headers, dict) else scope_or_headers
    for name, value in headers:
        if name == b"cookie":
            for part in value.decode("latin-1").split(";"):
                k, _, v = part.strip().partition("=")
                if k == COOKIE_NAME:
                    return v
    return None


# --------------------------------------------------------------------------- #
# Login rate limiting
# --------------------------------------------------------------------------- #
class LoginLimiter:
    """At most ``per_user`` failures per (address, username) and ``per_ip`` per address in ``window`` seconds."""

    def __init__(self, per_user: int = 5, per_ip: int = 20, window: float = 15 * 60):
        self.per_user = per_user
        self.per_ip = per_ip
        self.window = window
        self._fails: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._fails[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def retry_after(self, ip: str, username: str) -> int:
        """Seconds until another attempt is allowed (0 = allowed now)."""
        now = time.monotonic()
        with self._lock:
            waits = []
            for key, limit in ((f"ip:{ip}", self.per_ip), (f"user:{ip}:{username}", self.per_user)):
                q = self._recent(key, now)
                if len(q) >= limit:
                    waits.append(int(self.window - (now - q[0])) + 1)
            return max(waits, default=0)

    def failure(self, ip: str, username: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._fails[f"ip:{ip}"].append(now)
            self._fails[f"user:{ip}:{username}"].append(now)

    def success(self, ip: str, username: str) -> None:
        with self._lock:
            self._fails.pop(f"user:{ip}:{username}", None)

    def reset(self) -> None:
        with self._lock:
            self._fails.clear()


limiter = LoginLimiter()


# --------------------------------------------------------------------------- #
# Middleware
# --------------------------------------------------------------------------- #
def needs_session(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return False
    return path == "/api" or path.startswith(PROTECTED_PREFIXES)


class AuthMiddleware:
    """Pure ASGI middleware: a session for every protected path, and the learner fence."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not needs_session(scope["path"]):
            await self.app(scope, receive, send)
            return
        user = await run_in_threadpool(session_user, cookie_value(scope))
        if user is None:
            response = JSONResponse({"detail": "Please sign in."}, status_code=401, headers={"Cache-Control": "no-store"})
            await response(scope, receive, send)
            return
        if not user.is_admin and not learner_may_call(user, scope["method"], scope["path"]):
            # 404, not 403: a kid can't tell whether another learner (or a parent page) exists.
            response = JSONResponse({"detail": "Not found"}, status_code=404, headers={"Cache-Control": "no-store"})
            await response(scope, receive, send)
            return
        scope.setdefault("state", {})["user"] = user
        await self.app(scope, receive, send)
