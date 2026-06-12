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


def _biome(
    name: str, display: str, color: int, image: str | None = None,
    notify: bool = True, ping_everyone: bool = False,
) -> dict:
    return {
        "name": name,
        "display": display,
        "color": color,
        "image_url": image,
        "notify": notify,
        "ping_everyone": ping_everyone,
        "ping_role_id": None,
        "channel_id": None,
        "webhook_url": None,
        "webhook_broken": False,
    }


# Names must match Sol's RNG `largeImage.hoverText` exactly (uppercase).
# Colors and thumbnails follow the Coteab macro's biomes_data.json so embeds
# look consistent across community tools (their NORMAL entry mistakenly reuses
# the GLITCHED color/thumb; fixed here). Top-tier biomes ping @everyone by
# default; admins can turn that off or set a role per biome instead.
_THUMB = "https://maxstellar.github.io/biome_thumb"
_COTEAB = "https://raw.githubusercontent.com/xVapure/Noteab-Macro/refs/heads/main/images"

BIOME_SEED = [
    _biome("NORMAL", "Normal", 0x9B9B9B, f"{_THUMB}/NORMAL.png", notify=False),
    _biome("WINDY", "Windy", 0x9AE5FF, f"{_THUMB}/WINDY.png"),
    _biome("RAINY", "Rainy", 0x027CBD, f"{_THUMB}/RAINY.png"),
    _biome("SNOWY", "Snowy", 0xDCEFF9, f"{_THUMB}/SNOWY.png"),
    _biome("SAND STORM", "Sand Storm", 0x8F7057, f"{_THUMB}/SAND%20STORM.png"),
    _biome("HELL", "Hell", 0xFF4719, f"{_THUMB}/HELL.png"),
    _biome("STARFALL", "Starfall", 0x011AB7, f"{_THUMB}/STARFALL.png"),
    _biome("CORRUPTION", "Corruption", 0x6D32A8, f"{_THUMB}/CORRUPTION.png"),
    _biome("AURORA", "Aurora", 0x0047AB,
           "https://raw.githubusercontent.com/vexthecoder/OysterDetector/main/assets/aurora.png"),
    _biome("EGGLAND", "Eggland", 0xD4FC8D, f"{_COTEAB}/EGGLAND.png"),
    _biome("NULL", "Null", 0x838383, f"{_THUMB}/NULL.png"),
    _biome("HEAVEN", "Heaven", 0xFFE8A0, f"{_THUMB}/HEAVEN.png"),
    _biome("SINGULARITY", "Singularity", 0xCF4023, f"{_COTEAB}/SINGULARITY.png"),
    _biome("GLITCHED", "Glitched", 0xBFFF00, f"{_THUMB}/GLITCHED.png", ping_everyone=True),
    _biome("DREAMSPACE", "Dreamspace", 0xEA9DDA,
           f"{_COTEAB}/Screenshot_2026-01-03_021107.png", ping_everyone=True),
    _biome("CYBERSPACE", "Cyberspace", 0x0A1A3D, f"{_COTEAB}/CYBERSPACE.png",
           ping_everyone=True),
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
