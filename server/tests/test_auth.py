async def test_health_is_public(client):
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["server_name"] == "Test Community"


async def test_missing_key_rejected(client):
    resp = await client.get("/api/v1/me/config")
    assert resp.status == 401


async def test_unknown_key_rejected(client):
    resp = await client.get(
        "/api/v1/me/config", headers={"Authorization": "Bearer bb_does-not-exist"}
    )
    assert resp.status == 401


async def test_revoked_key_rejected(client, db, user, user_headers):
    await db.users.update_one({"discord_id": 111}, {"$set": {"active": False}})
    resp = await client.get("/api/v1/me/config", headers=user_headers)
    assert resp.status == 401


async def test_user_key_cannot_access_admin(client, user, user_headers):
    resp = await client.get("/api/v1/admin/stats", headers=user_headers)
    assert resp.status == 403


async def test_bootstrap_admin_token_works(client, admin_headers):
    resp = await client.get("/api/v1/admin/stats", headers=admin_headers)
    assert resp.status == 200


async def test_admin_requires_token(client):
    resp = await client.get("/api/v1/admin/stats")
    assert resp.status == 401


async def test_auth_updates_last_seen(client, db, user, user_headers):
    await client.get("/api/v1/me/config", headers=user_headers)
    doc = await db.users.find_one({"discord_id": 111})
    assert doc["last_seen"] is not None


async def test_rate_limit(client, user, user_headers):
    resp = None
    last = None
    for _ in range(35):
        resp = await client.get("/api/v1/me/config", headers=user_headers)
        last = resp.status
        if last == 429:
            break
    assert last == 429
    data = await resp.json()
    assert "retry_after" in data
