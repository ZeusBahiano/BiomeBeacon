from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ServerSettings:
    mongodb_uri: str
    db_name: str
    host: str
    port: int
    server_name: str
    admin_bootstrap_token: str
    log_level: str

    @classmethod
    def from_env(cls) -> ServerSettings:
        return cls(
            mongodb_uri=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"),
            db_name=os.environ.get("DB_NAME", "biomebeacon"),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8400")),
            server_name=os.environ.get("SERVER_NAME", "BiomeBeacon"),
            admin_bootstrap_token=os.environ.get("ADMIN_BOOTSTRAP_TOKEN", ""),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
