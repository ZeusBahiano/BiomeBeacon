"""Database bootstrap: indexes, default settings document and biome seed.

The document shapes here are the contract with the bot component — keep them in
sync with docs/DATA_MODEL.md.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

log = logging.getLogger(__name__)

SETTINGS_ID = "settings"
EVENTS_TTL_SECONDS = 30 * 24 * 3600

DISPATCH_MODES = ("single_channel", "per_biome_channels", "per_user_channels")

DEFAULT_SETTINGS: dict[str, Any] = {
    "guild_id": None,
    "dispatch_mode": "single_channel",
    "relay": True,
    "category_id": None,
    "single_channel_webhook": None,
    "single_channel_webhook_broken": False,
    "admin_role_id": None,
    "key_manager_role_id": None,
    "inactivity_days": 3,
    "inactivity_enabled": False,
    "min_macro_version": "0.0.0",
    "place_ids": [15532962292],
    "heartbeat_interval": 300,
    "updated_at": None,
}


def _biome(name: str, display: str, color: int, rarity: str, notify: bool = True) -> dict:
    return {
        "name": name,
        "display": display,
        "color": color,
        "image_url": None,
        "notify": notify,
        "ping_role_id": None,
        "channel_id": None,
        "webhook_url": None,
        "webhook_broken": False,
        "rarity": rarity,
    }


# Names must match Sol's RNG `largeImage.hoverText` exactly (uppercase).
BIOME_SEED = [
    _biome("NORMAL", "Normal", 0x9B9B9B, "common", notify=False),
    _biome("WINDY", "Windy", 0x8FD3E8, "common"),
    _biome("RAINY", "Rainy", 0x4F7DF2, "common"),
    _biome("SNOWY", "Snowy", 0xCFE8FF, "common"),
    _biome("SAND STORM", "Sand Storm", 0xD8B35A, "rare"),
    _biome("HELL", "Hell", 0xB3251E, "rare"),
    _biome("STARFALL", "Starfall", 0x6F6FD8, "rare"),
    _biome("CORRUPTION", "Corruption", 0x7D3BD1, "rare"),
    _biome("NULL", "Null", 0x222222, "legendary"),
    _biome("GLITCHED", "Glitched", 0x39FF14, "legendary"),
    _biome("DREAMSPACE", "Dreamspace", 0xFF7AD9, "legendary"),
]


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(dt: datetime) -> datetime:
    """PyMongo returns naive datetimes unless tz_aware is set; normalize before comparing."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def create_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)


async def get_settings(db: AsyncIOMotorDatabase) -> dict:
    doc = await db.settings.find_one({"_id": SETTINGS_ID})
    if doc is None:
        return {"_id": SETTINGS_ID, **DEFAULT_SETTINGS}
    # Tolerate documents created by older versions: fill missing keys.
    return {**DEFAULT_SETTINGS, **doc}


async def init_db(db: AsyncIOMotorDatabase) -> None:
    await db.settings.update_one(
        {"_id": SETTINGS_ID}, {"$setOnInsert": DEFAULT_SETTINGS}, upsert=True
    )
    for biome in BIOME_SEED:
        await db.biomes.update_one(
            {"name": biome["name"]}, {"$setOnInsert": biome}, upsert=True
        )

    indexes = [
        (db.users, [("key_hash", 1)], {"unique": True}),
        (db.users, [("discord_id", 1)], {"unique": True}),
        (db.biomes, [("name", 1)], {"unique": True}),
        (db.events, [("server_ts", 1)], {"expireAfterSeconds": EVENTS_TTL_SECONDS}),
        (db.events, [("user_id", 1), ("server_ts", -1)], {}),
        (db.admin_tokens, [("token_hash", 1)], {"unique": True}),
    ]
    for collection, keys, opts in indexes:
        try:
            await collection.create_index(keys, **opts)
        except Exception as exc:  # mongomock in tests does not support every option
            log.warning("create_index(%s, %s) failed: %s", collection.name, keys, exc)
