"""Request payload validation (pydantic v2)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Literal

from aiohttp import web
from pydantic import BaseModel, Field, ValidationError, field_validator

# Accepts the two real Roblox private-server link shapes:
#   https://www.roblox.com/games/<placeid>/...?privateServerLinkCode=<code>
#   https://www.roblox.com/share?code=<hex>&type=Server
PRIVATE_SERVER_RE = re.compile(
    r"^https://(www\.)?roblox\.com/"
    r"(games/\d+\S*[?&]privateServerLinkCode=[\w-]+|share\?code=[A-Za-z0-9]+&type=Server)$"
)


class EventIn(BaseModel):
    biome: str = Field(min_length=1, max_length=64)
    type: Literal["started", "ended"]
    client_ts: datetime
    roblox_user_id: int | None = None

    @field_validator("biome")
    @classmethod
    def normalize_biome(cls, v: str) -> str:
        return v.strip().upper()


class EventsPayload(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=20)


class HeartbeatIn(BaseModel):
    macro_version: str = "0.0.0"
    instances: int = Field(default=1, ge=0, le=50)


class PrivateServerPatch(BaseModel):
    link: str = Field(max_length=400)

    @field_validator("link")
    @classmethod
    def validate_link(cls, v: str) -> str:
        v = v.strip()
        if not PRIVATE_SERVER_RE.match(v):
            raise ValueError("not a valid Roblox private server link")
        return v


class SettingsPatch(BaseModel):
    dispatch_mode: Literal["single_channel", "per_biome_channels", "per_user_channels"] | None = (
        None
    )
    relay: bool | None = None
    single_channel_webhook: str | None = None
    admin_role_id: int | None = None
    key_manager_role_id: int | None = None
    inactivity_days: int | None = Field(default=None, ge=1, le=90)
    inactivity_enabled: bool | None = None
    min_macro_version: str | None = None
    place_ids: list[int] | None = None
    heartbeat_interval: int | None = Field(default=None, ge=60, le=3600)


class BiomePut(BaseModel):
    display: str = Field(min_length=1, max_length=64)
    color: int = Field(default=0x9B9B9B, ge=0, le=0xFFFFFF)
    image_url: str | None = None
    notify: bool = True
    ping_everyone: bool = False
    ping_role_id: int | None = None
    channel_id: int | None = None
    webhook_url: str | None = None


class TestWebhookIn(BaseModel):
    target: str = "single"  # "single" | "biome:<NAME>" | "user:<discord_id>"


async def parse_body(request: web.Request, model: type[BaseModel]) -> BaseModel:
    """Parses and validates a JSON body; raises HTTPUnprocessableEntity with details."""
    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "invalid JSON body"}), content_type="application/json"
        ) from None
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise web.HTTPUnprocessableEntity(
            text=json.dumps({"error": "validation failed", "details": details}),
            content_type="application/json",
        ) from None
