"""Inactivity purge: replaces the "channel janitor" bot communities use today.

A user whose macro hasn't been seen for `inactivity_days` (heartbeats and
events both refresh `last_seen`) gets their key deactivated and their channel
deleted, freeing Discord's channel limit.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import nextcord
from nextcord.ext import commands, tasks

from ..db import as_utc, get_settings, utcnow
from ..permissions import is_key_manager
from ..provisioning import delete_user_channel
from ..util import discord_ts

log = logging.getLogger(__name__)


async def find_inactive(db, settings: dict) -> list[dict]:
    """Active users whose last activity (or creation, if never seen) is too old."""
    cutoff = utcnow() - timedelta(days=settings["inactivity_days"])
    inactive = []
    async for user in db.users.find({"active": True}):
        reference = user.get("last_seen") or user.get("created_at")
        if reference is not None and as_utc(reference) < cutoff:
            inactive.append(user)
    return inactive


async def purge_inactive(db, guild: nextcord.Guild, settings: dict) -> list[dict]:
    purged = []
    for user in await find_inactive(db, settings):
        if user.get("channel_id"):
            await delete_user_channel(guild, user["channel_id"])
        await db.users.update_one(
            {"discord_id": user["discord_id"]},
            {"$set": {"active": False, "channel_id": None, "webhook_url": None}},
        )
        purged.append(user)
        log.info("purged inactive user %s (%s)", user.get("discord_name"), user["discord_id"])
    return purged


class InactivityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Started here (not in __init__) so a running event loop is guaranteed.
        if not self.purge_loop.is_running():
            self.purge_loop.start()

    def cog_unload(self):
        self.purge_loop.cancel()

    @tasks.loop(hours=6)
    async def purge_loop(self):
        settings = await get_settings(self.bot.db)
        if not settings.get("inactivity_enabled"):
            return
        guild = self.bot.get_guild(self.bot.guild_id)
        if guild is None:
            return
        purged = await purge_inactive(self.bot.db, guild, settings)
        if purged:
            log.info("inactivity purge removed %d user(s)", len(purged))

    @purge_loop.before_loop
    async def before_purge(self):
        await self.bot.wait_until_ready()

    # ---------------------------------------------------------------- /inactive

    @nextcord.slash_command(name="inactive", description="Manage inactive users")
    async def inactive_group(self, interaction: nextcord.Interaction):
        pass

    @inactive_group.subcommand(name="list", description="Who would be purged right now")
    async def inactive_list(self, interaction: nextcord.Interaction):
        settings = await get_settings(self.bot.db)
        if not is_key_manager(interaction.user, settings):
            await interaction.response.send_message(
                "You need the key-manager role (or admin) for this.", ephemeral=True
            )
            return
        inactive = await find_inactive(self.bot.db, settings)
        if not inactive:
            await interaction.response.send_message(
                f"No one inactive for {settings['inactivity_days']}+ days. 🎉", ephemeral=True
            )
            return
        lines = [
            f"<@{u['discord_id']}> — last seen {discord_ts(u.get('last_seen'))}"
            for u in inactive[:25]
        ]
        if len(inactive) > 25:
            lines.append(f"…and {len(inactive) - 25} more")
        await interaction.response.send_message(
            f"**{len(inactive)} user(s)** past the {settings['inactivity_days']}-day limit:\n"
            + "\n".join(lines),
            ephemeral=True,
        )

    @inactive_group.subcommand(name="purge", description="Purge them now (keys + channels)")
    async def inactive_purge(self, interaction: nextcord.Interaction):
        settings = await get_settings(self.bot.db)
        if not is_key_manager(interaction.user, settings):
            await interaction.response.send_message(
                "You need the key-manager role (or admin) for this.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        purged = await purge_inactive(self.bot.db, interaction.guild, settings)
        if not purged:
            await interaction.followup.send("Nothing to purge.")
            return
        names = ", ".join(f"<@{u['discord_id']}>" for u in purged[:20])
        await interaction.followup.send(
            f"Purged **{len(purged)}** user(s): {names}"
        )
