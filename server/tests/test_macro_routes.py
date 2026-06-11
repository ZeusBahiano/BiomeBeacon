async def test_config_shape_relay_mode(client, user, user_headers):
    resp = await client.get("/api/v1/me/config", headers=user_headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["user"]["discord_id"] == 111
    assert data["dispatch"]["relay"] is True
    assert data["dispatch"]["webhook_url"] is None
    names = {b["name"] for b in data["biomes"]}
    assert {"GLITCHED", "DREAMSPACE", "NORMAL"} <= names
    assert data["place_ids"] == [15532962292]


async def test_config_direct_mode_returns_webhook(client, db, user, user_headers):
    await db.settings.update_one(
        {"_id": "settings"},
        {"$set": {"relay": False, "dispatch_mode": "per_user_channels"}},
    )
    await db.users.update_one(
        {"discord_id": 111}, {"$set": {"webhook_url": "https://discord.com/api/webhooks/1/x"}}
    )
    resp = await client.get("/api/v1/me/config", headers=user_headers)
    data = await resp.json()
    assert data["dispatch"]["relay"] is False
    assert data["dispatch"]["webhook_url"] == "https://discord.com/api/webhooks/1/x"


async def test_direct_mode_ignored_outside_per_user(client, db, user, user_headers):
    # relay=false with single_channel must NOT leak the shared webhook
    await db.settings.update_one({"_id": "settings"}, {"$set": {"relay": False}})
    resp = await client.get("/api/v1/me/config", headers=user_headers)
    data = await resp.json()
    assert data["dispatch"]["relay"] is True
    assert data["dispatch"]["webhook_url"] is None


async def test_post_events_dispatches_and_audits(client, db, user, user_headers, dispatcher):
    payload = {
        "events": [
            {
                "biome": "glitched",  # normalized to uppercase
                "type": "started",
                "client_ts": "2026-06-11T12:00:00Z",
                "roblox_user_id": 1420234927,
            }
        ]
    }
    resp = await client.post("/api/v1/events", json=payload, headers=user_headers)
    assert resp.status == 200
    data = await resp.json()
    assert data == {"accepted": 1, "dispatched": 1}
    assert len(dispatcher.enqueued) == 1
    event, event_user, biome = dispatcher.enqueued[0]
    assert event["biome"] == "GLITCHED"
    assert biome["name"] == "GLITCHED"

    stored = await db.events.find_one({"biome": "GLITCHED"})
    assert stored["user_id"] == 111
    assert stored["dispatched"] is True

    updated = await db.users.find_one({"discord_id": 111})
    assert updated["last_event_at"] is not None
    assert 1420234927 in updated["roblox_user_ids"]


async def test_post_events_normal_is_audited_not_dispatched(
    client, db, user, user_headers, dispatcher
):
    payload = {
        "events": [{"biome": "NORMAL", "type": "started", "client_ts": "2026-06-11T12:00:00Z"}]
    }
    resp = await client.post("/api/v1/events", json=payload, headers=user_headers)
    data = await resp.json()
    assert data == {"accepted": 1, "dispatched": 0}
    assert dispatcher.enqueued == []
    assert await db.events.count_documents({}) == 1


async def test_post_events_unknown_biome(client, user, user_headers):
    payload = {
        "events": [{"biome": "FAKEBIOME", "type": "started", "client_ts": "2026-06-11T12:00:00Z"}]
    }
    resp = await client.post("/api/v1/events", json=payload, headers=user_headers)
    assert resp.status == 422
    data = await resp.json()
    assert "FAKEBIOME" in data["error"]


async def test_post_events_validates_payload(client, user, user_headers):
    resp = await client.post(
        "/api/v1/events",
        json={"events": [{"biome": "GLITCHED", "type": "exploded", "client_ts": "x"}]},
        headers=user_headers,
    )
    assert resp.status == 422


async def test_heartbeat_updates_user(client, db, user, user_headers):
    resp = await client.post(
        "/api/v1/heartbeat",
        json={"macro_version": "0.1.0", "instances": 3},
        headers=user_headers,
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True
    assert data["config_stale"] is False
    doc = await db.users.find_one({"discord_id": 111})
    assert doc["macro_version"] == "0.1.0"
    assert doc["instances"] == 3


async def test_heartbeat_rejects_old_macro(client, db, user, user_headers):
    await db.settings.update_one({"_id": "settings"}, {"$set": {"min_macro_version": "2.0.0"}})
    resp = await client.post(
        "/api/v1/heartbeat", json={"macro_version": "0.1.0"}, headers=user_headers
    )
    assert resp.status == 409
    data = await resp.json()
    assert data["min_version"] == "2.0.0"


async def test_heartbeat_config_stale_cycle(client, user, user_headers, admin_headers):
    # settings change marks configs stale...
    await client.patch(
        "/api/v1/admin/settings", json={"inactivity_days": 5}, headers=admin_headers
    )
    resp = await client.post("/api/v1/heartbeat", json={}, headers=user_headers)
    assert (await resp.json())["config_stale"] is True
    # ...until the macro re-fetches its config
    await client.get("/api/v1/me/config", headers=user_headers)
    resp = await client.post("/api/v1/heartbeat", json={}, headers=user_headers)
    assert (await resp.json())["config_stale"] is False


async def test_patch_private_server(client, db, user, user_headers):
    link = "https://www.roblox.com/games/15532962292/a?privateServerLinkCode=abc123"
    resp = await client.patch(
        "/api/v1/me/private-server", json={"link": link}, headers=user_headers
    )
    assert resp.status == 200
    doc = await db.users.find_one({"discord_id": 111})
    assert doc["private_server_link"] == link


async def test_patch_private_server_rejects_garbage(client, user, user_headers):
    for bad in ["https://evil.com/x", "not a link", "https://roblox.com/games/1"]:
        resp = await client.patch(
            "/api/v1/me/private-server", json={"link": bad}, headers=user_headers
        )
        assert resp.status == 422, bad
