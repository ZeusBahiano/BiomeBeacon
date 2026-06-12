"""Local macro configuration, persisted to %APPDATA%/BiomeBeacon/config.json.

Everything community-specific (biome list, dispatch mode, webhooks) lives on the
server and arrives via GET /me/config — the macro only stores how to reach it.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

log = logging.getLogger(__name__)


def default_roblox_log_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    return Path(local) / "Roblox" / "logs"


def config_dir() -> Path:
    base = os.environ.get("APPDATA", str(Path.home()))
    return Path(base) / "BiomeBeacon"


@dataclass
class MacroConfig:
    server_url: str = ""
    api_key: str = ""
    log_dir: str = ""  # empty = default Roblox location ("dev override" otherwise)
    start_minimized: bool = False
    poll_interval: float = 2.0
    theme: str = "void"

    @property
    def effective_log_dir(self) -> Path:
        return Path(self.log_dir) if self.log_dir else default_roblox_log_dir()

    @classmethod
    def load(cls) -> MacroConfig:
        path = config_dir() / "config.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("could not read %s (%s); using defaults", path, exc)
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        path = config_dir() / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
