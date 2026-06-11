"""Network worker: an asyncio event loop (aiohttp) running in its own thread.

Responsibilities:
- drain the detection queue and POST event batches to the server (always — the
  server is the audit log even in direct mode);
- in direct mode, additionally post the Discord webhook itself;
- heartbeat every `heartbeat_interval` (keeps `last_seen` fresh so the
  inactivity purge knows the hunter is alive) and re-fetch config when stale;
- resolve Roblox usernames for the UI;
- keep an offline buffer so a server blip never loses a GLITCHED alert.

UI-thread communication: thread-safe `ui_queue` out, public methods in (they
hop into the loop via call_soon_threadsafe / run_coroutine_threadsafe).
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime

import aiohttp

from ..config import MacroConfig
from ..detection.engine import BiomeEvent
from ..version import __version__
from .webhook import build_event_payload, post_webhook

log = logging.getLogger(__name__)

STOP = object()
CONFIG_REFRESH_SECONDS = 600.0
DEFAULT_HEARTBEAT_SECONDS = 300.0


class NetWorker(threading.Thread):
    def __init__(
        self,
        config: MacroConfig,
        events_queue: queue.Queue,
        ui_queue: queue.Queue,
        instances_fn: Callable[[], int] = lambda: 0,
        on_place_ids: Callable[[list[int]], None] = lambda ids: None,
    ):
        super().__init__(name="bb-net", daemon=True)
        self.config = config
        self.events_queue = events_queue
        self.ui_queue = ui_queue
        self.instances_fn = instances_fn
        self.on_place_ids = on_place_ids

        self.remote_config: dict | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._session: aiohttp.ClientSession | None = None
        self._refresh_now: asyncio.Event | None = None
        self._stopping: asyncio.Event | None = None
        self._pending: deque[dict] = deque(maxlen=100)
        self._usernames: dict[int, str] = {}

    # ---- thread-safe API for the UI thread ---------------------------------

    def stop(self) -> None:
        self.events_queue.put(STOP)

    def request_refresh(self) -> None:
        """Re-fetch /me/config (after the user saves new credentials, etc.)."""
        if self.loop and self._refresh_now:
            self.loop.call_soon_threadsafe(self._refresh_now.set)

    def submit_private_server(self, link: str) -> None:
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._patch_private_server(link), self.loop)

    # ---- loop scaffolding ---------------------------------------------------

    def run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        self.loop = asyncio.get_running_loop()
        self._refresh_now = asyncio.Event()
        self._stopping = asyncio.Event()
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        tasks = [
            asyncio.create_task(self._consumer()),
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._config_loop()),
        ]
        await self._stopping.wait()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._session.close()

    def _configured(self) -> bool:
        return bool(self.config.server_url and self.config.api_key)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def _url(self, path: str) -> str:
        return self.config.server_url.rstrip("/") + path

    def _status(self, connected: bool, text: str) -> None:
        self.ui_queue.put(("status", {"connected": connected, "text": text}))

    def _log(self, text: str) -> None:
        self.ui_queue.put(("log", text))

    # ---- event pipeline ------------------------------------------------------

    async def _consumer(self) -> None:
        while True:
            item = await asyncio.to_thread(self.events_queue.get)
            if item is STOP:
                self._stopping.set()
                return
            batch = [item]
            while len(batch) < 10:  # drain whatever piled up
                try:
                    extra = self.events_queue.get_nowait()
                except queue.Empty:
                    break
                if extra is STOP:
                    self._stopping.set()
                    return
                batch.append(extra)
            for event in batch:
                await self._handle_event(event)
            await self._flush()

    async def _handle_event(self, event: BiomeEvent) -> None:
        record = {
            "biome": event.biome,
            "type": event.type,
            "client_ts": datetime.fromtimestamp(event.ts, UTC).isoformat(),
            "roblox_user_id": event.roblox_user_id,
        }
        self._pending.append(record)
        self.ui_queue.put(("event", {**record, "instance": event.instance,
                                     "account": self._usernames.get(event.roblox_user_id)}))
        if event.roblox_user_id and event.roblox_user_id not in self._usernames:
            asyncio.create_task(self._resolve_username(event.roblox_user_id))
        await self._direct_dispatch(record)

    async def _direct_dispatch(self, record: dict) -> None:
        """Direct-webhook mode: post to Discord ourselves (per-user channels only)."""
        cfg = self.remote_config
        if not cfg or cfg["dispatch"].get("relay", True):
            return
        url = cfg["dispatch"].get("webhook_url")
        if not url:
            return
        biome = next((b for b in cfg["biomes"] if b["name"] == record["biome"]), None)
        if biome is None or not biome.get("notify", True):
            return
        payload = build_event_payload(record, cfg["user"], biome, cfg.get("server_name", ""))
        if await post_webhook(self._session, url, payload):
            self._log(f"webhook sent: {record['biome']} {record['type']}")
        else:
            self._log(f"webhook FAILED: {record['biome']} {record['type']}")

    async def _flush(self) -> None:
        """Send buffered events to the server; on failure they stay buffered."""
        if not self._pending or not self._configured():
            return
        batch = list(self._pending)[:20]
        payload = {"events": batch}
        try:
            async with self._session.post(
                self._url("/api/v1/events"), json=payload, headers=self._headers()
            ) as resp:
                if resp.status == 200:
                    for _ in batch:
                        self._pending.popleft()
                    data = await resp.json()
                    self._log(
                        f"server accepted {data.get('accepted', len(batch))} event(s), "
                        f"dispatched {data.get('dispatched', '?')}"
                    )
                elif resp.status == 401:
                    self._status(False, "Invalid or revoked API key")
                elif resp.status == 422:
                    detail = (await resp.json()).get("error", "rejected")
                    self._log(f"server rejected events: {detail}")
                    for _ in batch:  # don't retry a poisoned batch forever
                        self._pending.popleft()
                elif resp.status == 429:
                    pass  # keep buffered; next flush retries
        except aiohttp.ClientError as exc:
            self._status(False, "Server unreachable — buffering events")
            log.warning("event flush failed: %s", exc)

    # ---- heartbeat & config --------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        while True:
            interval = DEFAULT_HEARTBEAT_SECONDS
            if self.remote_config:
                interval = float(self.remote_config.get("heartbeat_interval", interval))
            await asyncio.sleep(interval)
            await self._flush()  # retry path for the offline buffer
            await self._heartbeat()

    async def _heartbeat(self) -> None:
        if not self._configured():
            return
        body = {"macro_version": __version__, "instances": self.instances_fn()}
        try:
            async with self._session.post(
                self._url("/api/v1/heartbeat"), json=body, headers=self._headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("config_stale"):
                        self._refresh_now.set()
                elif resp.status == 409:
                    data = await resp.json()
                    self._status(
                        False, f"Macro update required (min v{data.get('min_version', '?')})"
                    )
                elif resp.status == 401:
                    self._status(False, "Invalid or revoked API key")
        except aiohttp.ClientError as exc:
            log.debug("heartbeat failed: %s", exc)

    async def _config_loop(self) -> None:
        await self._fetch_config()
        await self._heartbeat()
        while True:
            try:
                await asyncio.wait_for(self._refresh_now.wait(), timeout=CONFIG_REFRESH_SECONDS)
            except TimeoutError:
                pass
            self._refresh_now.clear()
            await self._fetch_config()

    async def _fetch_config(self) -> None:
        if not self._configured():
            self._status(False, "Not configured — set Server URL and API Key in Settings")
            return
        try:
            async with self._session.get(
                self._url("/api/v1/me/config"), headers=self._headers()
            ) as resp:
                if resp.status == 200:
                    self.remote_config = await resp.json()
                    self.on_place_ids(self.remote_config.get("place_ids", []))
                    name = self.remote_config.get("server_name", "server")
                    mode = "relay" if self.remote_config["dispatch"]["relay"] else "direct"
                    self._status(True, f"Connected to {name} ({mode} mode)")
                    self.ui_queue.put(("config", self.remote_config))
                elif resp.status == 401:
                    self._status(False, "Invalid or revoked API key")
                else:
                    self._status(False, f"Server error HTTP {resp.status}")
        except aiohttp.ClientError as exc:
            self._status(False, "Server unreachable")
            log.warning("config fetch failed: %s", exc)

    async def _patch_private_server(self, link: str) -> None:
        if not self._configured():
            self._log("set Server URL and API Key first")
            return
        try:
            async with self._session.patch(
                self._url("/api/v1/me/private-server"),
                json={"link": link},
                headers=self._headers(),
            ) as resp:
                if resp.status == 200:
                    self._log("private server link updated ✔")
                    self._refresh_now.set()
                else:
                    data = await resp.json(content_type=None)
                    self._log(f"link rejected: {(data or {}).get('error', resp.status)}")
        except aiohttp.ClientError:
            self._log("could not update link (server unreachable)")

    async def _resolve_username(self, roblox_user_id: int) -> None:
        self._usernames[roblox_user_id] = str(roblox_user_id)  # placeholder, avoids refetch
        try:
            async with self._session.get(
                f"https://users.roblox.com/v1/users/{roblox_user_id}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    name = data.get("name") or str(roblox_user_id)
                    self._usernames[roblox_user_id] = name
                    self.ui_queue.put(("account", {"id": roblox_user_id, "name": name}))
        except aiohttp.ClientError:
            pass
