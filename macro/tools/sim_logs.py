"""Fake Roblox log writer — test the whole pipeline without launching the game.

Usage:
    python tools/sim_logs.py --biome GLITCHED --hold 30

Then, in the macro: Settings -> Advanced -> Log directory override -> the folder
this script prints. The script writes a fresh .log with the exact real-world
line format: a GameJoinLoadTime line, NORMAL, then your biome, then back to
NORMAL after --hold seconds. Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

JOIN_TEMPLATE = (
    "{ts},1.323562,22e8,6 [FLog::GameJoinLoadTime] Report game_join_loadtime: "
    "placeid:{place_id}, join_time:0.5781, universeid:5361032378, "
    "referral_page:RequestPrivateGame, sid:00000000-0000-0000-0000-000000000000, "
    "clienttime:{epoch}, userid:{user_id},"
)
RPC_TEMPLATE = "{ts},3.478098,22e8,6 [FLog::Output] [BloxstrapRPC] {payload}"


def rpc_payload(biome: str) -> str:
    return json.dumps(
        {
            "command": "SetRichPresence",
            "data": {
                "state": "Equipped _None_",
                "smallImage": {"hoverText": "Sol's RNG", "assetId": 126196647942405},
                "largeImage": {"hoverText": biome, "assetId": 80690294537387},
            },
        },
        separators=(",", ":"),
    )


def now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=str(Path(tempfile.gettempdir()) / "bb_fake_logs"))
    parser.add_argument("--biome", default="GLITCHED")
    parser.add_argument("--hold", type=float, default=30.0, help="seconds the biome lasts")
    parser.add_argument("--delay", type=float, default=8.0, help="seconds before it starts")
    parser.add_argument("--userid", type=int, default=1420234927)
    parser.add_argument("--place", type=int, default=15532962292)
    args = parser.parse_args()

    log_dir = Path(args.dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"0.000.0.0_{int(time.time())}_Player_SIM_last.log"

    def write(line: str) -> None:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        print(f"  wrote: {line[:110]}{'…' if len(line) > 110 else ''}")

    print(f"Point the macro's log directory override at:\n  {log_dir}\n")
    write(
        JOIN_TEMPLATE.format(
            ts=now_ts(), place_id=args.place, epoch=f"{time.time():.6f}", user_id=args.userid
        )
    )
    write(RPC_TEMPLATE.format(ts=now_ts(), payload=rpc_payload("NORMAL")))

    print(f"\n{args.biome} starts in {args.delay:.0f}s…")
    time.sleep(args.delay)
    write(RPC_TEMPLATE.format(ts=now_ts(), payload=rpc_payload(args.biome)))

    print(f"{args.biome} ACTIVE for {args.hold:.0f}s (Ctrl+C to stop early)")
    try:
        deadline = time.time() + args.hold
        while time.time() < deadline:
            time.sleep(5)
            # keepalive so the watcher keeps treating this instance as active
            write(RPC_TEMPLATE.format(ts=now_ts(), payload=rpc_payload(args.biome)))
    except KeyboardInterrupt:
        pass

    write(RPC_TEMPLATE.format(ts=now_ts(), payload=rpc_payload("NORMAL")))
    print("biome ended — done.")


if __name__ == "__main__":
    main()
