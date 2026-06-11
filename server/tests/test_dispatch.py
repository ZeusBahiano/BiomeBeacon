"""Dispatcher unit tests: webhook resolution, payload building, broken marking.

No real HTTP here — delivery is exercised in the e2e flow with webhook_sink.
"""

from datetime import timedelta

import pytest
from biomebeacon_server.db import init_db, utcnow
from biomebeacon_server.dispatch import ENDED_COLOR, Dispatcher
from mongomock_motor import AsyncMongoMockClient

WEBHOOK = "https://discord.com/api/webhooks/123/abc"


@pytest.fixture
def db():
    return AsyncMongoMockClient()["testdb"]


@pytest.fixture
async def dispatcher(db):
    await init_db(db)
    return Dispatcher(db, "Test Community")


def _user(**extra):
    link = "https://www.roblox.com/share?code=x&type=Server"
    return {"discord_id": 111, "private_server_link": link, **extra}


def _biome(**extra):
    return {"name": "GLITCHED", "display": "Glitched", "color": 0x39FF14,
            "notify": True, "ping_role_id": None, "webhook_url": None, **extra}


def _event(type_="started", **extra):
    return {"user_id": 111, "biome": "GLITCHED", "type": type_, "server_ts": utcnow(), **extra}


def test_resolve_webhook_modes(dispatcher):
    user = _user(webhook_url="user-hook")
    biome = _biome(webhook_url="biome-hook")
    assert (
        dispatcher._resolve_webhook(
            {"dispatch_mode": "single_channel", "single_channel_webhook": "single-hook"},
            user, biome,
        )
        == "single-hook"
    )
    assert (
        dispatcher._resolve_webhook({"dispatch_mode": "per_biome_channels"}, user, biome)
        == "biome-hook"
    )
    assert (
        dispatcher._resolve_webhook({"dispatch_mode": "per_user_channels"}, user, biome)
        == "user-hook"
    )


def test_payload_started_pings_and_links(dispatcher):
    payload = dispatcher.build_payload(_event(), _user(), _biome(ping_role_id=42))
    assert payload["content"] == "<@&42>"
    assert payload["allowed_mentions"] == {"parse": ["roles"]}
    embed = payload["embeds"][0]
    assert embed["title"] == "Glitched started!"
    assert embed["color"] == 0x39FF14
    assert "<@111>" in embed["description"]
    assert "Join now" in embed["description"]
    assert payload["username"] == "Test Community"


def test_payload_started_without_link(dispatcher):
    payload = dispatcher.build_payload(_event(), _user(private_server_link=None), _biome())
    assert "_not set_" in payload["embeds"][0]["description"]
    assert payload["content"] == ""  # no ping role configured


def test_payload_ended_is_gray_and_silent(dispatcher):
    payload = dispatcher.build_payload(_event("ended"), _user(), _biome(ping_role_id=42), 12.3)
    embed = payload["embeds"][0]
    assert embed["title"] == "Glitched ended"
    assert embed["color"] == ENDED_COLOR
    assert "Lasted:** 12 min" in embed["description"]
    assert payload["content"] == ""  # ended never pings


async def test_enqueue_requires_configured_webhook(dispatcher, db):
    queued = await dispatcher.enqueue_event(_event(), _user(), _biome())
    assert queued is False  # single_channel mode, no webhook set

    await db.settings.update_one(
        {"_id": "settings"}, {"$set": {"single_channel_webhook": WEBHOOK}}
    )
    queued = await dispatcher.enqueue_event(_event(), _user(), _biome())
    assert queued is True
    assert dispatcher.queue.qsize() == 1


async def test_ended_duration_lookup(dispatcher, db):
    started_at = utcnow() - timedelta(minutes=10)
    await db.events.insert_one(_event("started", server_ts=started_at))
    minutes = await dispatcher._find_duration(_event("ended"))
    assert minutes == pytest.approx(10, abs=0.5)


async def test_mark_broken_per_mode(dispatcher, db):
    await db.users.insert_one(_user())
    await dispatcher._mark_broken({"mode": "single_channel"})
    settings = await db.settings.find_one({"_id": "settings"})
    assert settings["single_channel_webhook_broken"] is True

    await dispatcher._mark_broken({"mode": "per_biome_channels", "biome": "GLITCHED"})
    biome = await db.biomes.find_one({"name": "GLITCHED"})
    assert biome["webhook_broken"] is True

    await dispatcher._mark_broken({"mode": "per_user_channels", "user_id": 111})
    stored = await db.users.find_one({"discord_id": 111})
    assert stored["webhook_broken"] is True


async def test_send_test_targets(dispatcher, db):
    assert await dispatcher.send_test("single") is False  # nothing configured
    await db.settings.update_one(
        {"_id": "settings"}, {"$set": {"single_channel_webhook": WEBHOOK}}
    )
    assert await dispatcher.send_test("single") is True
    assert await dispatcher.send_test("biome:NOPE") is False
    assert await dispatcher.send_test("user:notanint") is False
