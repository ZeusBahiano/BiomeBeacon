"""Per-instance biome state machine.

One Roblox process = one log file = one InstanceState. A change in the RPC
hoverText emits `ended(previous)` + `started(new)`. The biome list itself is
server-side config — the engine reports any transition and lets the server (or
the direct-mode sender) decide what is notify-worthy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .parser import GAME_NAME, GameJoin, RpcUpdate, parse_line


@dataclass(frozen=True)
class BiomeEvent:
    biome: str
    type: str  # "started" | "ended"
    ts: float  # unix epoch
    instance: str  # log file key
    roblox_user_id: int | None


@dataclass
class InstanceState:
    instance: str
    biome: str | None = None
    biome_since: float | None = None
    roblox_user_id: int | None = None
    place_id: int | None = None
    in_target_game: bool = False


@dataclass
class DetectionEngine:
    place_ids: list[int] = field(default_factory=list)
    instances: dict[str, InstanceState] = field(default_factory=dict)

    def process_line(self, instance: str, line: str, now: float | None = None) -> list[BiomeEvent]:
        parsed = parse_line(line)
        if parsed is None:
            return []
        now = time.time() if now is None else now
        state = self.instances.setdefault(instance, InstanceState(instance))

        if isinstance(parsed, GameJoin):
            state.place_id = parsed.place_id
            if parsed.roblox_user_id:
                state.roblox_user_id = parsed.roblox_user_id
            state.in_target_game = not self.place_ids or parsed.place_id in self.place_ids
            return []

        assert isinstance(parsed, RpcUpdate)
        if parsed.game is not None:
            if parsed.game != GAME_NAME:
                return []  # RPC from some other game in this client
            state.in_target_game = True
        elif not state.in_target_game:
            return []  # unidentified RPC before we ever saw Sol's RNG

        if parsed.biome == state.biome:
            return []

        events: list[BiomeEvent] = []
        if state.biome is not None:
            events.append(
                BiomeEvent(state.biome, "ended", now, instance, state.roblox_user_id)
            )
        events.append(BiomeEvent(parsed.biome, "started", now, instance, state.roblox_user_id))
        state.biome = parsed.biome
        state.biome_since = now
        return events

    def drop_instance(self, instance: str) -> None:
        """Roblox closed (log went quiet). No synthetic 'ended' is emitted: the
        biome keeps running on the private server even after this player leaves,
        and log rotation must not fake biome endings."""
        self.instances.pop(instance, None)

    def snapshot(self) -> list[InstanceState]:
        return list(self.instances.values())
