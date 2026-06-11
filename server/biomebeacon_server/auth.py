"""Bearer authentication middleware, key hashing and per-key rate limiting.

Key hashing must stay byte-identical to bot/biomebeacon_bot/keys.py — the parity
test vector lives in docs/DATA_MODEL.md.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import deque

from aiohttp import web

from .db import utcnow

USER_KEY_PREFIX = "bb_"
ADMIN_TOKEN_PREFIX = "bba_"
RATE_LIMIT = 30  # requests
RATE_WINDOW = 60.0  # seconds

PUBLIC_PATHS = {"/", "/health"}
PUBLIC_PREFIXES = ("/admin", "/static")


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_key(prefix: str = USER_KEY_PREFIX) -> tuple[str, str, str]:
    """Returns (key, key_hash, key_prefix). The key itself must be shown once and discarded."""
    key = prefix + secrets.token_urlsafe(32)
    return key, hash_key(key), key[:8]


def json_error(status: int, message: str, **extra) -> web.Response:
    return web.json_response({"error": message, **extra}, status=status)


class RateLimiter:
    def __init__(self, limit: int = RATE_LIMIT, window: float = RATE_WINDOW):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> float | None:
        """Returns None if allowed, otherwise seconds until the next slot frees up."""
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return round(self.window - (now - hits[0]), 1)
        hits.append(now)
        return None


def _bearer(request: web.Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return None


async def _check_admin(request: web.Request, token: str | None) -> web.Response | None:
    if not token:
        return json_error(401, "missing admin token")
    bootstrap = request.app["settings"].admin_bootstrap_token
    if bootstrap and hmac.compare_digest(token, bootstrap):
        request["admin"] = {"label": "bootstrap", "discord_id": None}
        return None
    if token.startswith(USER_KEY_PREFIX):
        return json_error(403, "user keys cannot access admin endpoints")
    doc = await request.app["db"].admin_tokens.find_one(
        {"token_hash": hash_key(token), "active": True}
    )
    if doc is None:
        return json_error(401, "invalid admin token")
    request["admin"] = doc
    return None


async def _check_user(request: web.Request, token: str | None) -> web.Response | None:
    if not token:
        return json_error(401, "missing API key")
    retry = request.app["rate_limiter"].check(hash_key(token))
    if retry is not None:
        return json_error(429, "rate limited", retry_after=retry)
    doc = await request.app["db"].users.find_one({"key_hash": hash_key(token), "active": True})
    if doc is None:
        return json_error(401, "invalid or revoked API key")
    request["user"] = doc
    await request.app["db"].users.update_one(
        {"_id": doc["_id"]}, {"$set": {"last_seen": utcnow()}}
    )
    return None


@web.middleware
async def auth_middleware(request: web.Request, handler):
    path = request.path
    if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return await handler(request)

    token = _bearer(request)
    if path.startswith("/api/v1/admin"):
        error = await _check_admin(request, token)
    elif path.startswith("/api/v1/"):
        error = await _check_user(request, token)
    else:
        return json_error(404, "not found")
    if error is not None:
        return error
    return await handler(request)
