"""End-to-end pipeline test, no Roblox/Discord/Mongo required:

fake log file -> LogWatcher -> DetectionEngine -> NetWorker HTTP -> real server
app (mongomock db, REAL dispatcher) -> webhook delivery over real HTTP -> sink.

Only the GUI and the real external services are out of the loop.
"""

import asyncio
import queue

import pytest
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient, TestServer
from biomebeacon.config import MacroConfig
from biomebeacon.detection.engine import DetectionEngine
from biomebeacon.detection.watcher import LogWatcher
from biomebeacon.net.client import NetWorker
from biomebeacon_server.app import create_app
from biomebeacon_server.auth import hash_key
from biomebeacon_server.db import utcnow
from biomebeacon_server.settings import ServerSettings
from mongomock_motor import AsyncMongoMockClient

TEST_KEY = "bb_unittest-key-000"

JOIN_LINE = (
    "x [FLog::GameJoinLoadTime] Report game_join_loadtime: placeid:15532962292, "
    "userid:1420234927,"
)
RPC = (
    '... [FLog::Output] [BloxstrapRPC] {{"command":"SetRichPresence","data":{{'
    '"state":"x","smallImage":{{"hoverText":"Sol\'s RNG","assetId":1}},'
    '"largeImage":{{"hoverText":"{biome}","assetId":2}}}}}}'
)


@pytest.fixture
async def sink():
    """Fake Discord webhook endpoint capturing payloads."""
    received: list[dict] = []

    async def handle(request: web.Request) -> web.Response:
        received.append(await request.json())
        return web.Response(status=204)

    app = web.Application()
    app.router.add_post("/webhook", handle)
    server = TestServer(app)
    await server.start_server()
    yield server, received
    await server.close()


async def test_full_pipeline(tmp_path, sink):
    sink_server, received = sink

    # --- server side: real app + real dispatcher on a real local port --------
    db = AsyncMongoMockClient()["e2e"]
    settings = ServerSettings(
        mongodb_uri="unused", db_name="e2e", host="127.0.0.1", port=0,
        server_name="E2E Community", admin_bootstrap_token="bba_e2e", log_level="WARNING",
    )
    server_app = create_app(settings=settings, db=db)
    server = TestClient(TestServer(server_app))
    await server.start_server()
    try:
        await db.users.insert_one(
            {
                "discord_id": 111,
                "discord_name": "lucas",
                "key_hash": hash_key(TEST_KEY),
                "key_prefix": TEST_KEY[:8],
                "private_server_link": "https://www.roblox.com/share?code=e2e1&type=Server",
                "active": True,
                "created_at": utcnow(),
                "roblox_user_ids": [],
            }
        )
        await db.settings.update_one(
            {"_id": "settings"},
            {"$set": {"single_channel_webhook": str(sink_server.make_url("/webhook"))}},
        )

        # --- macro side: real watcher/engine fed by a fake log file ----------
        log_file = tmp_path / "0.1_SIM_Player_last.log"
        log_file.write_text(JOIN_LINE + "\n" + RPC.format(biome="NORMAL") + "\n")

        events_q: queue.Queue = queue.Queue()
        ui_q: queue.Queue = queue.Queue()
        engine = DetectionEngine()
        watcher = LogWatcher(tmp_path, engine, events_q, ui_q)

        watcher.scan_once()  # first sight: seeds silently
        assert events_q.empty()
        assert engine.instances[log_file.name].biome == "NORMAL"

        with log_file.open("a") as fh:
            fh.write(RPC.format(biome="GLITCHED") + "\n")
        watcher.scan_once()
        assert not events_q.empty()

        # --- macro net layer: real HTTP against the real server --------------
        config = MacroConfig(
            server_url=str(server.make_url("")).rstrip("/"), api_key=TEST_KEY
        )
        worker = NetWorker(config, events_q, ui_q)
        async with ClientSession() as session:
            worker._session = session
            while not events_q.empty():
                await worker._handle_event(events_q.get_nowait())
            await worker._flush()

        # --- assertions across the whole chain --------------------------------
        dispatcher = server_app["dispatcher"]
        await asyncio.wait_for(dispatcher.queue.join(), timeout=5)

        started = [
            p for p in received
            if p["embeds"][0]["title"].startswith("Glitched started")
        ]
        assert started, f"no GLITCHED alert reached the webhook sink: {received}"
        embed = started[0]["embeds"][0]
        assert "Join now" in embed["description"]
        assert started[0]["username"] == "E2E Community"

        stored = await db.events.find_one({"biome": "GLITCHED", "type": "started"})
        assert stored is not None and stored["dispatched"] is True
        assert stored["roblox_user_id"] == 1420234927

        user = await db.users.find_one({"discord_id": 111})
        assert user["last_seen"] is not None
        assert 1420234927 in user["roblox_user_ids"]
    finally:
        await server.close()
