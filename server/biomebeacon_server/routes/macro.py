"""Endpoints used by the macro (user-key authenticated). See docs/API.md."""

from __future__ import annotations

from aiohttp import web

from .. import __version__
from ..auth import json_error
from ..db import as_utc, get_settings, utcnow
from ..models import EventsPayload, HeartbeatIn, PrivateServerPatch, parse_body

routes = web.RouteTableDef()


def _version_tuple(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.strip().split("."))
    except ValueError:
        return (0,)


@routes.get("/health")
async def health(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "name": "BiomeBeacon Server",
            "version": __version__,
            "server_name": request.app["settings"].server_name,
        }
    )


@routes.get("/api/v1/me/config")
async def me_config(request: web.Request) -> web.Response:
    db = request.app["db"]
    user = request["user"]
    settings = await get_settings(db)

    # Direct-webhook mode is only honored with per-user channels; anything else
    # would hand every user the shared webhooks, which must stay server-side.
    relay = settings["relay"] or settings["dispatch_mode"] != "per_user_channels"
    webhook_url = None if relay else user.get("webhook_url")

    biomes = [
        {
            "name": b["name"],
            "display": b.get("display") or b["name"].title(),
            "color": b.get("color", 0x9B9B9B),
            "image_url": b.get("image_url"),
            "notify": b.get("notify", True),
            "ping_role_id": b.get("ping_role_id"),
        }
        async for b in db.biomes.find({})
    ]
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"config_fetched_at": utcnow()}})
    return web.json_response(
        {
            "user": {
                "discord_id": user["discord_id"],
                "discord_name": user.get("discord_name"),
                "private_server_link": user.get("private_server_link"),
            },
            "dispatch": {"relay": relay, "webhook_url": webhook_url},
            "biomes": biomes,
            "place_ids": settings["place_ids"],
            "heartbeat_interval": settings["heartbeat_interval"],
            "min_macro_version": settings["min_macro_version"],
            "server_name": request.app["settings"].server_name,
        }
    )


@routes.post("/api/v1/events")
async def post_events(request: web.Request) -> web.Response:
    payload: EventsPayload = await parse_body(request, EventsPayload)
    db = request.app["db"]
    user = request["user"]
    dispatcher = request.app["dispatcher"]
    settings = await get_settings(db)

    names = {e.biome for e in payload.events}
    found = {b["name"]: b async for b in db.biomes.find({"name": {"$in": list(names)}})}
    unknown = names - found.keys()
    if unknown:
        return json_error(422, f"unknown biomes: {', '.join(sorted(unknown))}")

    accepted = dispatched = 0
    now = utcnow()
    for ev in payload.events:
        biome = found[ev.biome]
        doc = {
            "user_id": user["discord_id"],
            "biome": ev.biome,
            "type": ev.type,
            "client_ts": ev.client_ts,
            "server_ts": now,
            "private_server_link": user.get("private_server_link"),
            "roblox_user_id": ev.roblox_user_id,
            "macro_version": user.get("macro_version"),
            "dispatched": False,
        }
        if settings["relay"] and biome.get("notify", True):
            doc["dispatched"] = await dispatcher.enqueue_event(doc, user, biome)
            dispatched += int(doc["dispatched"])
        await db.events.insert_one(doc)
        accepted += 1

    update: dict = {"$set": {"last_event_at": now}}
    roblox_ids = [e.roblox_user_id for e in payload.events if e.roblox_user_id]
    if roblox_ids:
        update["$addToSet"] = {"roblox_user_ids": {"$each": roblox_ids}}
    await db.users.update_one({"_id": user["_id"]}, update)
    return web.json_response({"accepted": accepted, "dispatched": dispatched})


@routes.post("/api/v1/heartbeat")
async def heartbeat(request: web.Request) -> web.Response:
    hb: HeartbeatIn = await parse_body(request, HeartbeatIn)
    db = request.app["db"]
    user = request["user"]
    settings = await get_settings(db)

    if _version_tuple(hb.macro_version) < _version_tuple(settings["min_macro_version"]):
        return json_error(
            409, "macro update required", min_version=settings["min_macro_version"]
        )

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"macro_version": hb.macro_version, "instances": hb.instances}},
    )
    fetched = user.get("config_fetched_at")
    updated = settings.get("updated_at")
    stale = bool(updated and (not fetched or as_utc(updated) > as_utc(fetched)))
    return web.json_response({"ok": True, "config_stale": stale})


@routes.patch("/api/v1/me/private-server")
async def patch_private_server(request: web.Request) -> web.Response:
    patch: PrivateServerPatch = await parse_body(request, PrivateServerPatch)
    db = request.app["db"]
    user = request["user"]
    await db.users.update_one(
        {"_id": user["_id"]}, {"$set": {"private_server_link": patch.link}}
    )
    return web.json_response({"ok": True, "link": patch.link})
