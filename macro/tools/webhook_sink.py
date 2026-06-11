"""Local stand-in for a Discord webhook: prints whatever it receives.

Usage:
    python tools/webhook_sink.py [--port 9999]

Then set the server's webhook to http://localhost:9999/webhook (dashboard ->
Settings -> single channel webhook, or via /setup) and watch alerts arrive here.
"""

from __future__ import annotations

import argparse
import json

from aiohttp import web


async def handle(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except ValueError:
        payload = {"raw": await request.text()}
    print(f"\n=== webhook received on {request.path} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return web.Response(status=204)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9999)
    args = parser.parse_args()

    app = web.Application()
    app.router.add_post("/{tail:.*}", handle)
    print(f"webhook sink listening on http://localhost:{args.port}/webhook")
    web.run_app(app, port=args.port, print=None)


if __name__ == "__main__":
    main()
