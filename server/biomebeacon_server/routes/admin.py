"""Admin endpoints (admin-token authenticated). See docs/API.md.

User *creation* intentionally lives in the bot (`/key create`) because it
provisions Discord channels and webhooks; everything else is manageable here.
"""

from __future__ import annotations

from datetime import timedelta

from aiohttp import web

from ..auth import generate_key, json_error
from ..db import DEFAULT_SETTINGS, SETTINGS_ID, get_settings, utcnow
from ..models import (
    PRIVATE_SERVER_RE,
    BiomePut,
    SettingsPatch,
    TestWebhookIn,
    parse_body,
)
from . import jsonable

routes = web.RouteTableDef()

USER_PROJECTION = {"key_hash": 0}


def _parse_discord_id(request: web.Request) -> int:
    try:
        return int(request.match_info["discord_id"])
    except ValueError:
        raise web.HTTPBadRequest(
            text='{"error": "discord_id must be an integer"}', content_type="application/json"
        ) from None


@routes.get("/api/v1/admin/stats")
async def stats(request: web.Request) -> web.Response:
    db = request.app["db"]
    settings = await get_settings(db)
    since = utcnow() - timedelta(hours=24)
    broken: list[str] = []
    if settings.get("single_channel_webhook_broken"):
        broken.append("single_channel")
    broken += [f"biome:{b['name']}" async for b in db.biomes.find({"webhook_broken": True})]
    broken += [
        f"user:{u['discord_id']}" async for u in db.users.find({"webhook_broken": True})
    ]
    return web.json_response(
        {
            "users_total": await db.users.count_documents({}),
            "users_active": await db.users.count_documents({"active": True}),
            "events_24h": await db.events.count_documents({"server_ts": {"$gte": since}}),
            "dispatch_mode": settings["dispatch_mode"],
            "relay": settings["relay"],
            "broken_webhooks": broken,
        }
    )


@routes.get("/api/v1/admin/users")
async def list_users(request: web.Request) -> web.Response:
    db = request.app["db"]
    query: dict = {}
    if request.query.get("active") in ("true", "false"):
        query["active"] = request.query["active"] == "true"
    users = [
        jsonable(u)
        async for u in db.users.find(query, USER_PROJECTION).sort("created_at", -1)
    ]
    return web.json_response({"users": users})


@routes.get("/api/v1/admin/users/{discord_id}")
async def get_user(request: web.Request) -> web.Response:
    db = request.app["db"]
    user = await db.users.find_one({"discord_id": _parse_discord_id(request)}, USER_PROJECTION)
    if user is None:
        return json_error(404, "user not found")
    return web.json_response(jsonable(user))


@routes.patch("/api/v1/admin/users/{discord_id}")
async def patch_user(request: web.Request) -> web.Response:
    db = request.app["db"]
    discord_id = _parse_discord_id(request)
    try:
        body = await request.json()
    except Exception:
        return json_error(400, "invalid JSON body")
    updates: dict = {}
    if "active" in body:
        if not isinstance(body["active"], bool):
            return json_error(422, "active must be a boolean")
        updates["active"] = body["active"]
    if "private_server_link" in body:
        link = body["private_server_link"]
        if link is not None and not PRIVATE_SERVER_RE.match(str(link).strip()):
            return json_error(422, "not a valid Roblox private server link")
        updates["private_server_link"] = link and str(link).strip()
    if not updates:
        return json_error(422, "nothing to update (allowed: active, private_server_link)")
    result = await db.users.update_one({"discord_id": discord_id}, {"$set": updates})
    if result.matched_count == 0:
        return json_error(404, "user not found")
    return web.json_response({"ok": True, **jsonable(updates)})


@routes.post("/api/v1/admin/users/{discord_id}/regenerate-key")
async def regenerate_key(request: web.Request) -> web.Response:
    db = request.app["db"]
    discord_id = _parse_discord_id(request)
    key, key_hash, key_prefix = generate_key()
    result = await db.users.update_one(
        {"discord_id": discord_id},
        {"$set": {"key_hash": key_hash, "key_prefix": key_prefix, "active": True}},
    )
    if result.matched_count == 0:
        return json_error(404, "user not found")
    # Returned exactly once; only the hash is stored.
    return web.json_response({"key": key, "key_prefix": key_prefix})


@routes.delete("/api/v1/admin/users/{discord_id}")
async def delete_user(request: web.Request) -> web.Response:
    db = request.app["db"]
    result = await db.users.delete_one({"discord_id": _parse_discord_id(request)})
    if result.deleted_count == 0:
        return json_error(404, "user not found")
    return web.json_response({"ok": True})


@routes.get("/api/v1/admin/settings")
async def get_settings_route(request: web.Request) -> web.Response:
    settings = await get_settings(request.app["db"])
    return web.json_response(jsonable(settings))


@routes.patch("/api/v1/admin/settings")
async def patch_settings(request: web.Request) -> web.Response:
    db = request.app["db"]
    patch: SettingsPatch = await parse_body(request, SettingsPatch)
    updates = patch.model_dump(exclude_none=True)
    current = await get_settings(db)
    merged = {**current, **updates}
    if not merged["relay"] and merged["dispatch_mode"] != "per_user_channels":
        return json_error(
            422, "relay=false (direct webhooks) requires dispatch_mode=per_user_channels"
        )
    if "single_channel_webhook" in updates:
        updates["single_channel_webhook_broken"] = False
    updates["updated_at"] = utcnow()
    await db.settings.update_one(
        {"_id": SETTINGS_ID}, {"$setOnInsert": DEFAULT_SETTINGS, "$set": updates}, upsert=True
    )
    return web.json_response(jsonable({**merged, **updates}))


@routes.get("/api/v1/admin/biomes")
async def list_biomes(request: web.Request) -> web.Response:
    db = request.app["db"]
    biomes = [jsonable(b) async for b in db.biomes.find({}).sort("name", 1)]
    return web.json_response({"biomes": biomes})


@routes.put("/api/v1/admin/biomes/{name}")
async def put_biome(request: web.Request) -> web.Response:
    db = request.app["db"]
    name = request.match_info["name"].strip().upper()
    body: BiomePut = await parse_body(request, BiomePut)
    doc = {"name": name, **body.model_dump(), "webhook_broken": False}
    await db.biomes.update_one({"name": name}, {"$set": doc}, upsert=True)
    await db.settings.update_one({"_id": SETTINGS_ID}, {"$set": {"updated_at": utcnow()}})
    return web.json_response(jsonable(doc))


@routes.delete("/api/v1/admin/biomes/{name}")
async def delete_biome(request: web.Request) -> web.Response:
    db = request.app["db"]
    name = request.match_info["name"].strip().upper()
    result = await db.biomes.delete_one({"name": name})
    if result.deleted_count == 0:
        return json_error(404, "biome not found")
    await db.settings.update_one({"_id": SETTINGS_ID}, {"$set": {"updated_at": utcnow()}})
    return web.json_response({"ok": True})


@routes.get("/api/v1/admin/events")
async def list_events(request: web.Request) -> web.Response:
    db = request.app["db"]
    query: dict = {}
    if request.query.get("user"):
        try:
            query["user_id"] = int(request.query["user"])
        except ValueError:
            return json_error(422, "user must be a discord id (integer)")
    if request.query.get("biome"):
        query["biome"] = request.query["biome"].strip().upper()
    limit = min(int(request.query.get("limit", "50") or 50), 500)
    events = [
        jsonable(e) async for e in db.events.find(query).sort("server_ts", -1).limit(limit)
    ]
    return web.json_response({"events": events})


@routes.post("/api/v1/admin/test-webhook")
async def test_webhook(request: web.Request) -> web.Response:
    body: TestWebhookIn = await parse_body(request, TestWebhookIn)
    sent = await request.app["dispatcher"].send_test(body.target)
    if not sent:
        return json_error(404, f"no webhook configured for target '{body.target}'")
    return web.json_response({"ok": True})
