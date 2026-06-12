"""Webhook dispatcher: a single async worker drains a queue of Discord deliveries.

Biome transitions are rare (a handful per hour per user), so sequential delivery
with polite 429 handling is plenty. A webhook that returns 401/404/410 is flagged
as broken on the owning document so it shows up in the dashboard.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from .db import as_utc, get_settings

log = logging.getLogger(__name__)

ENDED_COLOR = 0x4F545C
TEST_COLOR = 0x7C3AED


class Dispatcher:
    def __init__(self, db, server_name: str):
        self.db = db
        self.server_name = server_name
        self.queue: asyncio.Queue[tuple[str, dict, dict]] = asyncio.Queue()
        self._session: aiohttp.ClientSession | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()

    # -- enqueueing ---------------------------------------------------------

    async def enqueue_event(self, event: dict, user: dict, biome: dict) -> bool:
        """Queues a webhook delivery for a biome event. Returns False when the
        active dispatch mode has no webhook configured for this event."""
        settings = await get_settings(self.db)
        url = self._resolve_webhook(settings, user, biome)
        if not url:
            return False
        duration = None
        if event["type"] == "ended":
            duration = await self._find_duration(event)
        payload = self.build_payload(event, user, biome, duration)
        meta = {
            "mode": settings["dispatch_mode"],
            "user_id": user.get("discord_id"),
            "biome": biome["name"],
        }
        await self.queue.put((url, payload, meta))
        return True

    async def send_test(self, target: str) -> bool:
        """target: "single" | "biome:<NAME>" | "user:<discord_id>" (admin endpoint)."""
        settings = await get_settings(self.db)
        url = None
        meta = {"mode": "test", "target": target}
        if target == "single":
            url = settings.get("single_channel_webhook")
            meta["mode"] = "single_channel"
        elif target.startswith("biome:"):
            biome = await self.db.biomes.find_one({"name": target[6:].strip().upper()})
            if biome:
                url = biome.get("webhook_url")
                meta.update(mode="per_biome_channels", biome=biome["name"])
        elif target.startswith("user:"):
            try:
                discord_id = int(target[5:])
            except ValueError:
                return False
            user = await self.db.users.find_one({"discord_id": discord_id})
            if user:
                url = user.get("webhook_url")
                meta.update(mode="per_user_channels", user_id=discord_id)
        if not url:
            return False
        payload = {
            "username": self.server_name,
            "embeds": [
                {
                    "title": "Webhook test",
                    "description": "The BiomeBeacon server can reach this webhook.",
                    "color": TEST_COLOR,
                }
            ],
        }
        await self.queue.put((url, payload, meta))
        return True

    def _resolve_webhook(self, settings: dict, user: dict, biome: dict) -> str | None:
        mode = settings["dispatch_mode"]
        if mode == "single_channel":
            return settings.get("single_channel_webhook")
        if mode == "per_biome_channels":
            return biome.get("webhook_url")
        if mode == "per_user_channels":
            return user.get("webhook_url")
        return None

    async def _find_duration(self, event: dict) -> float | None:
        """Minutes since the matching `started` event, for the `ended` embed."""
        prev = await self.db.events.find_one(
            {"user_id": event["user_id"], "biome": event["biome"], "type": "started"},
            sort=[("server_ts", -1)],
        )
        if not prev:
            return None
        delta = (as_utc(event["server_ts"]) - as_utc(prev["server_ts"])).total_seconds()
        if delta <= 0 or delta > 6 * 3600:  # stale match, don't show nonsense
            return None
        return delta / 60

    # -- payload ------------------------------------------------------------

    def build_payload(
        self, event: dict, user: dict, biome: dict, duration_min: float | None = None
    ) -> dict:
        started = event["type"] == "started"
        display = biome.get("display") or biome["name"].title()
        lines = [f"**User:** <@{user['discord_id']}>"]
        if started:
            link = user.get("private_server_link")
            lines.append(
                f"**Private server:** [Join now]({link})"
                if link
                else "**Private server:** _not set_"
            )
        elif duration_min is not None:
            lines.append(f"**Lasted:** {duration_min:.0f} min")
        if event.get("roblox_user_id"):
            lines.append(f"**Account:** `{event['roblox_user_id']}`")

        embed = {
            "title": f"{display} started!" if started else f"{display} ended",
            "description": "\n".join(lines),
            "color": biome.get("color", 0x9B9B9B) if started else ENDED_COLOR,
            "timestamp": event["server_ts"].isoformat(),
            "footer": {"text": f"{self.server_name} • BiomeBeacon"},
        }
        if biome.get("image_url"):
            embed["thumbnail"] = {"url": biome["image_url"]}

        content = ""
        if started and biome.get("ping_role_id"):
            content = f"<@&{biome['ping_role_id']}>"
        return {
            "username": self.server_name,
            "content": content,
            "embeds": [embed],
            "allowed_mentions": {"parse": ["roles"]},
        }

    # -- delivery -----------------------------------------------------------

    async def _worker(self) -> None:
        while True:
            url, payload, meta = await self.queue.get()
            try:
                await self._deliver(url, payload, meta)
            except Exception:
                log.exception("webhook delivery failed (%s)", meta)
            finally:
                self.queue.task_done()

    async def _deliver(self, url: str, payload: dict, meta: dict) -> None:
        assert self._session is not None
        for _attempt in range(3):
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (200, 204):
                    return
                if resp.status == 429:
                    data = await resp.json(content_type=None)
                    retry = float((data or {}).get("retry_after", 1.0))
                    await asyncio.sleep(min(retry, 10.0))
                    continue
                if resp.status in (401, 404, 410):
                    log.error("webhook gone (%s): HTTP %s", meta, resp.status)
                    await self._mark_broken(meta)
                    return
                body = await resp.text()
                log.error("webhook error %s (%s): %s", resp.status, meta, body[:300])
                return
        log.error("webhook delivery gave up after retries (%s)", meta)

    async def _mark_broken(self, meta: dict) -> None:
        mode = meta.get("mode")
        if mode == "single_channel":
            await self.db.settings.update_one(
                {"_id": "settings"}, {"$set": {"single_channel_webhook_broken": True}}
            )
        elif mode == "per_biome_channels" and meta.get("biome"):
            await self.db.biomes.update_one(
                {"name": meta["biome"]}, {"$set": {"webhook_broken": True}}
            )
        elif mode == "per_user_channels" and meta.get("user_id") is not None:
            await self.db.users.update_one(
                {"discord_id": meta["user_id"]}, {"$set": {"webhook_broken": True}}
            )
