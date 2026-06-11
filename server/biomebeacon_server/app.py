from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

from .auth import RateLimiter, auth_middleware
from .db import create_client, init_db
from .dispatch import Dispatcher
from .routes.admin import routes as admin_routes
from .routes.macro import routes as macro_routes
from .settings import ServerSettings

DASHBOARD_DIR = Path(__file__).parent / "dashboard"


async def _redirect_root(_request: web.Request) -> web.Response:
    raise web.HTTPFound("/admin")


async def _dashboard_index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(DASHBOARD_DIR / "index.html")


async def _on_startup(app: web.Application) -> None:
    await init_db(app["db"])
    await app["dispatcher"].start()


async def _on_cleanup(app: web.Application) -> None:
    await app["dispatcher"].stop()
    client = app.get("mongo_client")
    if client is not None:
        client.close()


def create_app(
    settings: ServerSettings | None = None,
    db=None,
    dispatcher: Dispatcher | None = None,
) -> web.Application:
    """App factory. `db` and `dispatcher` are injectable for tests."""
    settings = settings or ServerSettings.from_env()
    app = web.Application(middlewares=[auth_middleware])
    app["settings"] = settings
    if db is None:
        client = create_client(settings.mongodb_uri)
        app["mongo_client"] = client
        db = client[settings.db_name]
    app["db"] = db
    app["dispatcher"] = dispatcher or Dispatcher(db, settings.server_name)
    app["rate_limiter"] = RateLimiter()

    app.add_routes(macro_routes)
    app.add_routes(admin_routes)
    app.router.add_get("/", _redirect_root)
    app.router.add_get("/admin", _dashboard_index)
    app.router.add_static("/static", DASHBOARD_DIR / "static")

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app


def main() -> None:
    settings = ServerSettings.from_env()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    web.run_app(create_app(settings), host=settings.host, port=settings.port)
