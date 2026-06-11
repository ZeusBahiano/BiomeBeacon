from __future__ import annotations

import logging
import os

import nextcord
from dotenv import load_dotenv
from nextcord.ext import commands

from .db import create_client

log = logging.getLogger(__name__)


class BiomeBeaconBot(commands.Bot):
    def __init__(self, *, guild_id: int, db, public_server_url: str):
        # Default intents are enough: slash commands deliver members directly,
        # so no privileged intents are required.
        super().__init__(intents=nextcord.Intents.default(), default_guild_ids=[guild_id])
        self.db = db
        self.guild_id = guild_id
        self.public_server_url = public_server_url

    async def on_ready(self):
        log.info("logged in as %s (guild %s)", self.user, self.guild_id)


def build_bot() -> tuple[BiomeBeaconBot, str]:
    load_dotenv()
    token = os.environ.get("DISCORD_TOKEN", "")
    guild_raw = os.environ.get("GUILD_ID", "")
    if not token or not guild_raw.isdigit():
        raise SystemExit("DISCORD_TOKEN and GUILD_ID must be set (see .env.example)")

    client = create_client(os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "biomebeacon")]
    bot = BiomeBeaconBot(
        guild_id=int(guild_raw),
        db=db,
        public_server_url=os.environ.get("PUBLIC_SERVER_URL", "http://localhost:8400"),
    )

    from .cogs.inactivity import InactivityCog
    from .cogs.keys import KeysCog
    from .cogs.setup import SetupCog

    bot.add_cog(SetupCog(bot))
    bot.add_cog(KeysCog(bot))
    bot.add_cog(InactivityCog(bot))
    return bot, token


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bot, token = build_bot()
    bot.run(token)
