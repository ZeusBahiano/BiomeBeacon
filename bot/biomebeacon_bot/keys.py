"""Key generation/hashing and private-server link validation.

Hashing must stay byte-identical to server/biomebeacon_server/auth.py — the
parity vector lives in docs/DATA_MODEL.md and is asserted by tests on both sides.
"""

from __future__ import annotations

import hashlib
import re
import secrets

USER_KEY_PREFIX = "bb_"
ADMIN_TOKEN_PREFIX = "bba_"

PRIVATE_SERVER_RE = re.compile(
    r"^https://(www\.)?roblox\.com/"
    r"(games/\d+\S*[?&]privateServerLinkCode=[\w-]+|share\?code=[A-Za-z0-9]+&type=Server)$"
)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_key(prefix: str = USER_KEY_PREFIX) -> tuple[str, str, str]:
    """Returns (key, key_hash, key_prefix). Show the key once, store only the hash."""
    key = prefix + secrets.token_urlsafe(32)
    return key, hash_key(key), key[:8]


def generate_admin_token() -> tuple[str, str, str]:
    token = ADMIN_TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, hash_key(token), token[:9]


def valid_private_server_link(link: str) -> bool:
    return bool(PRIVATE_SERVER_RE.match(link.strip()))
