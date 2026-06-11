from datetime import timedelta
from types import SimpleNamespace

from biomebeacon_bot.cogs.inactivity import find_inactive
from biomebeacon_bot.db import utcnow
from biomebeacon_bot.provisioning import channel_name_for
from mongomock_motor import AsyncMongoMockClient


async def test_find_inactive_logic():
    db = AsyncMongoMockClient()["testdb"]
    now = utcnow()
    await db.users.insert_many(
        [
            # stale: last_seen 5 days ago
            {"discord_id": 1, "active": True, "last_seen": now - timedelta(days=5),
             "created_at": now - timedelta(days=30)},
            # fresh: seen an hour ago
            {"discord_id": 2, "active": True, "last_seen": now - timedelta(hours=1),
             "created_at": now - timedelta(days=30)},
            # already revoked: ignored even though stale
            {"discord_id": 3, "active": False, "last_seen": now - timedelta(days=9),
             "created_at": now - timedelta(days=30)},
            # never ran the macro, created long ago -> purged
            {"discord_id": 4, "active": True, "last_seen": None,
             "created_at": now - timedelta(days=10)},
            # never ran the macro but just got the key -> grace period
            {"discord_id": 5, "active": True, "last_seen": None, "created_at": now},
        ]
    )
    inactive = await find_inactive(db, {"inactivity_days": 3})
    assert {u["discord_id"] for u in inactive} == {1, 4}


def test_channel_name_sanitization():
    m = SimpleNamespace(display_name="Lucas DZ!! ✨", name="lucas", id=42)
    assert channel_name_for(m) == "biome-lucas-dz"

    weird = SimpleNamespace(display_name="✨✨✨", name="✨", id=42)
    assert channel_name_for(weird) == "biome-42"
