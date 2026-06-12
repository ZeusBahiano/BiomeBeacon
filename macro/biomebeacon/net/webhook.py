"""Direct-webhook mode: the macro builds and posts the Discord embed itself.

Mirrors the server dispatcher's payload (server/biomebeacon_server/dispatch.py)
so both flows look identical in Discord.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

log = logging.getLogger(__name__)

ENDED_COLOR = 0x4F545C


def build_event_payload(event: dict, user: dict, biome: dict, server_name: str) -> dict:
    started = event["type"] == "started"
    display = biome.get("display") or event["biome"].title()
    lines = [f"**User:** <@{user['discord_id']}>"]
    if started:
        link = user.get("private_server_link")
        lines.append(
            f"**Private server:** [Join now]({link})" if link else "**Private server:** _not set_"
        )
    if event.get("roblox_user_id"):
        lines.append(f"**Account:** `{event['roblox_user_id']}`")

    embed = {
        "title": f"{display} started!" if started else f"{display} ended",
        "description": "\n".join(lines),
        "color": biome.get("color", 0x9B9B9B) if started else ENDED_COLOR,
        "timestamp": event["client_ts"],
        "footer": {"text": f"{server_name} • BiomeBeacon"},
    }
    if biome.get("image_url"):
        embed["thumbnail"] = {"url": biome["image_url"]}

    content = ""
    if started and biome.get("ping_role_id"):
        content = f"<@&{biome['ping_role_id']}>"
    return {
        "username": server_name,
        "content": content,
        "embeds": [embed],
        "allowed_mentions": {"parse": ["roles"]},
    }


async def post_webhook(session: aiohttp.ClientSession, url: str, payload: dict) -> bool:
    for _attempt in range(3):
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status in (200, 204):
                    return True
                if resp.status == 429:
                    data = await resp.json(content_type=None)
                    await asyncio.sleep(min(float((data or {}).get("retry_after", 1.0)), 10.0))
                    continue
                log.error("webhook returned HTTP %s", resp.status)
                return False
        except aiohttp.ClientError as exc:
            log.warning("webhook post failed: %s", exc)
            return False
    return False
