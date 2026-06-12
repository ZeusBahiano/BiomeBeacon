async def test_stats(client, db, user, admin_headers):
    resp = await client.get("/api/v1/admin/stats", headers=admin_headers)
    data = await resp.json()
    assert data["users_total"] == 1
    assert data["users_active"] == 1
    assert data["dispatch_mode"] == "single_channel"
    assert data["broken_webhooks"] == []


async def test_users_list_hides_hash_and_stringifies_snowflakes(client, db, admin_headers):
    from biomebeacon_server.auth import hash_key
    from biomebeacon_server.db import utcnow

    big_id = 1420234927000000000  # > 2^53 — must come back as a string
    await db.users.insert_one(
        {
            "discord_id": big_id,
            "discord_name": "snowflake",
            "key_hash": hash_key("bb_whatever"),
            "key_prefix": "bb_whate",
            "active": True,
            "created_at": utcnow(),
        }
    )
    resp = await client.get("/api/v1/admin/users", headers=admin_headers)
    data = await resp.json()
    assert len(data["users"]) == 1
    listed = data["users"][0]
    assert "key_hash" not in listed
    assert listed["discord_id"] == str(big_id)


async def test_patch_user_deactivates(client, db, user, user_headers, admin_headers):
    resp = await client.patch(
        "/api/v1/admin/users/111", json={"active": False}, headers=admin_headers
    )
    assert resp.status == 200
    resp = await client.get("/api/v1/me/config", headers=user_headers)
    assert resp.status == 401


async def test_patch_user_validates(client, user, admin_headers):
    resp = await client.patch(
        "/api/v1/admin/users/111", json={"private_server_link": "https://evil.com"},
        headers=admin_headers,
    )
    assert resp.status == 422
    resp = await client.patch("/api/v1/admin/users/111", json={}, headers=admin_headers)
    assert resp.status == 422
    resp = await client.patch(
        "/api/v1/admin/users/999", json={"active": True}, headers=admin_headers
    )
    assert resp.status == 404


async def test_regenerate_key_rotates_access(client, db, user, user_headers, admin_headers):
    resp = await client.post(
        "/api/v1/admin/users/111/regenerate-key", headers=admin_headers
    )
    assert resp.status == 200
    new_key = (await resp.json())["key"]
    assert new_key.startswith("bb_")

    # old key is dead, new key works
    resp = await client.get("/api/v1/me/config", headers=user_headers)
    assert resp.status == 401
    resp = await client.get(
        "/api/v1/me/config", headers={"Authorization": f"Bearer {new_key}"}
    )
    assert resp.status == 200


async def test_delete_user(client, user, admin_headers):
    resp = await client.delete("/api/v1/admin/users/111", headers=admin_headers)
    assert resp.status == 200
    resp = await client.delete("/api/v1/admin/users/111", headers=admin_headers)
    assert resp.status == 404


async def test_settings_patch_validates_relay_mode(client, admin_headers):
    resp = await client.patch(
        "/api/v1/admin/settings", json={"relay": False}, headers=admin_headers
    )
    assert resp.status == 422  # single_channel + direct would leak the shared webhook

    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"relay": False, "dispatch_mode": "per_user_channels"},
        headers=admin_headers,
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["relay"] is False
    assert data["updated_at"] is not None


async def test_settings_patch_rejects_unknown_mode(client, admin_headers):
    resp = await client.patch(
        "/api/v1/admin/settings", json={"dispatch_mode": "carrier_pigeon"},
        headers=admin_headers,
    )
    assert resp.status == 422


async def test_biome_put_and_delete(client, db, admin_headers):
    resp = await client.put(
        "/api/v1/admin/biomes/pumpkin moon",
        json={"display": "Pumpkin Moon", "color": 0xFF8800, "ping_everyone": True},
        headers=admin_headers,
    )
    assert resp.status == 200
    doc = await db.biomes.find_one({"name": "PUMPKIN MOON"})
    assert doc["display"] == "Pumpkin Moon"

    resp = await client.delete("/api/v1/admin/biomes/PUMPKIN MOON", headers=admin_headers)
    assert resp.status == 200
    assert await db.biomes.find_one({"name": "PUMPKIN MOON"}) is None


async def test_events_listing_filters(client, db, user, user_headers, admin_headers):
    for biome in ("GLITCHED", "RAINY"):
        await client.post(
            "/api/v1/events",
            json={"events": [{"biome": biome, "type": "started",
                              "client_ts": "2026-06-11T12:00:00Z"}]},
            headers=user_headers,
        )
    resp = await client.get(
        "/api/v1/admin/events?biome=glitched", headers=admin_headers
    )
    data = await resp.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["biome"] == "GLITCHED"


async def test_test_webhook_endpoint(client, dispatcher, admin_headers):
    resp = await client.post(
        "/api/v1/admin/test-webhook", json={"target": "single"}, headers=admin_headers
    )
    assert resp.status == 200
    assert dispatcher.test_targets == ["single"]

    dispatcher.test_result = False
    resp = await client.post(
        "/api/v1/admin/test-webhook", json={"target": "user:999"}, headers=admin_headers
    )
    assert resp.status == 404
