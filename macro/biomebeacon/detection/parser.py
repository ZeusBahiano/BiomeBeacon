"""Pure parsing of Roblox client log lines.

Ground truth (real log lines from a live Sol's RNG session):

  ... [FLog::Output] [BloxstrapRPC] {"command":"SetRichPresence","data":{
      "state":"Equipped _None_",
      "smallImage":{"hoverText":"Sol's RNG","assetId":126196647942405},
      "largeImage":{"hoverText":"RAINY","assetId":137992545432987}}}

  ... [FLog::GameJoinLoadTime] Report game_join_loadtime: placeid:15532962292,
      ..., referral_page:RequestPrivateGame, ..., userid:1420234927,

The biome lives in data.largeImage.hoverText; the game identifies itself in
data.smallImage.hoverText. The game prints these lines for every player — no
Bloxstrap installation is required.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

GAME_NAME = "Sol's RNG"

RPC_MARKER = "[BloxstrapRPC]"
RPC_RE = re.compile(r"\[BloxstrapRPC\] (\{.*\})")
JOIN_MARKER = "[FLog::GameJoinLoadTime]"
PLACE_RE = re.compile(r"placeid:(\d+)")
USERID_RE = re.compile(r"userid:(\d+)")


@dataclass(frozen=True)
class RpcUpdate:
    biome: str  # uppercase, e.g. "SAND STORM"
    game: str | None  # smallImage hoverText, e.g. "Sol's RNG"


@dataclass(frozen=True)
class GameJoin:
    place_id: int
    roblox_user_id: int | None


def parse_line(line: str) -> RpcUpdate | GameJoin | None:
    if RPC_MARKER in line:
        match = RPC_RE.search(line)
        if not match:
            return None
        try:
            payload = json.loads(match.group(1))
        except ValueError:
            return None
        if payload.get("command") != "SetRichPresence":
            return None
        data = payload.get("data") or {}
        biome = ((data.get("largeImage") or {}).get("hoverText") or "").strip()
        game = (data.get("smallImage") or {}).get("hoverText")
        if not biome:
            return None
        return RpcUpdate(biome=biome.upper(), game=game)

    if JOIN_MARKER in line:
        place = PLACE_RE.search(line)
        if not place:
            return None
        user = USERID_RE.search(line)
        return GameJoin(
            place_id=int(place.group(1)),
            roblox_user_id=int(user.group(1)) if user else None,
        )

    return None
