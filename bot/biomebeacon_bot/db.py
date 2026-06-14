"""Mongo access for the bot. Document shapes are the contract with the server
component — see docs/DATA_MODEL.md before changing anything here."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

SETTINGS_ID = "settings"

# Mirror of the server defaults (docs/DATA_MODEL.md). The bot must behave even if
# it starts before the server has ever run.
DEFAULT_SETTINGS: dict[str, Any] = {
    "guild_id": None,
    "dispatch_mode": "single_channel",
    "relay": True,
    "category_id": None,
    "single_channel_webhook": None,
    "single_channel_webhooks": [],  # extra webhooks for the same channel (round-robin)
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


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def create_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)


async def get_settings(db: AsyncIOMotorDatabase) -> dict:
    doc = await db.settings.find_one({"_id": SETTINGS_ID})
    if doc is None:
        return {"_id": SETTINGS_ID, **DEFAULT_SETTINGS}
    return {**DEFAULT_SETTINGS, **doc}


async def update_settings(db: AsyncIOMotorDatabase, updates: dict) -> None:
    """Settings changes also bump updated_at so macros re-fetch their config."""
    set_doc = {**updates, "updated_at": utcnow()}
    # Mongo rejects upserts where $set and $setOnInsert share a path (code 40),
    # so only seed the defaults that this update does not already touch.
    on_insert = {k: v for k, v in DEFAULT_SETTINGS.items() if k not in set_doc}
    await db.settings.update_one(
        {"_id": SETTINGS_ID},
        {"$setOnInsert": on_insert, "$set": set_doc},
        upsert=True,
    )
