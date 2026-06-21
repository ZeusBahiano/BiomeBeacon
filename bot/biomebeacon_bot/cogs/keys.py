"""/key — user key lifecycle — and /myserver for self-service link updates."""

from __future__ import annotations

import logging

import nextcord
from nextcord import SlashOption
from nextcord.ext import commands

from ..db import get_settings, utcnow
from ..keys import generate_key, valid_private_server_link
from ..permissions import is_key_manager
from ..provisioning import (
    create_user_channel,
    delete_user_channel,
    grant_member_role,
    revoke_member_role,
)
from ..util import discord_ts

log = logging.getLogger(__name__)


class KeysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _gate_manager(self, interaction: nextcord.Interaction) -> dict | None:
        settings = await get_settings(self.bot.db)
        if not is_key_manager(interaction.user, settings):
            await interaction.response.send_message(
                "You need the key-manager role (or admin) for this.", ephemeral=True
            )
            return None
        return settings

    async def _send_key_dm(self, member: nextcord.Member, key: str) -> bool:
        embed = nextcord.Embed(
            title="Your BiomeBeacon access",
            color=0x7C3AED,
            description=(
                "Open the BiomeBeacon macro → **Settings** and paste these:\n\n"
                f"**Server URL:** `{self.bot.public_server_url}`\n"
                f"**API Key:** ||`{key}`||\n\n"
                "The key is shown **only once** — keep it secret. "
                "Set or update your private server with `/myserver` or in the macro."
            ),
        )
        try:
            await member.send(embed=embed)
            return True
        except nextcord.HTTPException:
            return False

    # -------------------------------------------------------------------- /key

    @nextcord.slash_command(name="key", description="Manage user keys")
    async def key_group(self, interaction: nextcord.Interaction):
        pass

    @key_group.subcommand(name="create", description="Create a key (and channel) for a user")
    async def key_create(
        self,
        interaction: nextcord.Interaction,
        member: nextcord.Member = SlashOption(description="The user"),
        private_server: str = SlashOption(
            description="Their Roblox private server link", required=False
        ),
    ):
        settings = await self._gate_manager(interaction)
        if settings is None:
            return
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db

        if private_server and not valid_private_server_link(private_server):
            await interaction.followup.send(
                "That doesn't look like a Roblox private server link "
                "(`roblox.com/...privateServerLinkCode=...` or `roblox.com/share?code=...`)."
            )
            return

        existing = await db.users.find_one({"discord_id": member.id})
        if existing and existing.get("active"):
            await interaction.followup.send(
                f"{member.mention} already has an active key — use `/key regenerate` instead."
            )
            return

        channel_id = existing.get("channel_id") if existing else None
        webhook_url = existing.get("webhook_url") if existing else None
        notes = []
        if settings["dispatch_mode"] == "per_user_channels":
            # Per-user mode grants access via a role — refuse to issue a key until one is set.
            role_id = settings.get("member_role_id")
            member_role = interaction.guild.get_role(role_id) if role_id else None
            if member_role is None:
                reason = (
                    "the configured member role no longer exists"
                    if role_id
                    else "no member role is set"
                )
                await interaction.followup.send(
                    f"Per-user channel mode requires a member role, but {reason} — "
                    "configure it with `/setup roles member:` first."
                )
                return

            channel = interaction.guild.get_channel(channel_id) if channel_id else None
            if channel is None:
                try:
                    channel_id, webhook_url = await create_user_channel(
                        interaction.guild, member, settings.get("category_id"), member_role
                    )
                except nextcord.Forbidden:
                    await interaction.followup.send(
                        "I need **Manage Channels** and **Manage Webhooks** to create "
                        "the user's channel."
                    )
                    return
                notes.append(f"Channel created: <#{channel_id}>")
            else:
                # Reused channel: keep the member role's read access in sync.
                try:
                    await channel.set_permissions(
                        member_role,
                        view_channel=True,
                        read_message_history=True,
                        reason="BiomeBeacon: verified members can view",
                    )
                except nextcord.Forbidden:
                    pass

            try:
                await grant_member_role(member, member_role)
            except nextcord.Forbidden:
                await interaction.followup.send(
                    f"I need **Manage Roles** (with my role above {member_role.mention}) "
                    "to grant access."
                )
                return
            notes.append(f"Granted {member_role.mention}.")

        key, key_hash, key_prefix = generate_key()
        fields = {
            "discord_name": member.display_name or member.name,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "channel_id": channel_id,
            "webhook_url": webhook_url,
            "webhook_broken": False,
            "active": True,
        }
        if private_server:
            fields["private_server_link"] = private_server.strip()
        if existing:
            await db.users.update_one({"discord_id": member.id}, {"$set": fields})
            notes.append("Existing record reactivated with a fresh key.")
        else:
            await db.users.insert_one(
                {
                    "discord_id": member.id,
                    "private_server_link": private_server.strip() if private_server else None,
                    "created_at": utcnow(),
                    "created_by": interaction.user.id,
                    "last_seen": None,
                    "last_event_at": None,
                    "macro_version": None,
                    "roblox_user_ids": [],
                    **fields,
                }
            )

        if await self._send_key_dm(member, key):
            notes.append("Key delivered via DM.")
        else:
            notes.append(
                f"⚠️ {member.mention} has DMs closed — pass this on (shown once): ||`{key}`||"
            )
        await interaction.followup.send(
            f"Key created for {member.mention}.\n" + "\n".join(notes)
        )

    @key_group.subcommand(name="revoke", description="Revoke a user's access")
    async def key_revoke(
        self,
        interaction: nextcord.Interaction,
        member: nextcord.Member = SlashOption(description="The user"),
        delete_channel: bool = SlashOption(
            description="Also delete their channel (default: yes)", required=False
        ),
    ):
        settings = await self._gate_manager(interaction)
        if settings is None:
            return
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db
        user = await db.users.find_one({"discord_id": member.id})
        if user is None:
            await interaction.followup.send(f"{member.mention} has no key.")
            return
        delete_channel = True if delete_channel is None else delete_channel
        updates = {"active": False, "webhook_url": None}
        notes = [f"Access revoked for {member.mention}."]
        if delete_channel and user.get("channel_id"):
            if await delete_user_channel(interaction.guild, user["channel_id"]):
                notes.append("Channel deleted.")
            updates["channel_id"] = None
        # Per-user mode: drop the access role too.
        if settings["dispatch_mode"] == "per_user_channels":
            role_id = settings.get("member_role_id")
            member_role = interaction.guild.get_role(role_id) if role_id else None
            if member_role is not None and await revoke_member_role(member, member_role):
                notes.append(f"Removed {member_role.mention}.")
        await db.users.update_one({"discord_id": member.id}, {"$set": updates})
        await interaction.followup.send("\n".join(notes))

    @key_group.subcommand(name="regenerate", description="Issue a fresh key (old one dies)")
    async def key_regenerate(
        self,
        interaction: nextcord.Interaction,
        member: nextcord.Member = SlashOption(description="The user"),
    ):
        settings = await self._gate_manager(interaction)
        if settings is None:
            return
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db
        user = await db.users.find_one({"discord_id": member.id})
        if user is None:
            await interaction.followup.send(
                f"{member.mention} has no key yet — use `/key create`."
            )
            return
        key, key_hash, key_prefix = generate_key()
        await db.users.update_one(
            {"discord_id": member.id},
            {"$set": {"key_hash": key_hash, "key_prefix": key_prefix, "active": True}},
        )
        if await self._send_key_dm(member, key):
            await interaction.followup.send(f"New key sent to {member.mention} via DM.")
        else:
            await interaction.followup.send(
                f"⚠️ {member.mention} has DMs closed — pass this on (shown once): ||`{key}`||"
            )

    @key_group.subcommand(name="info", description="Inspect a user's status")
    async def key_info(
        self,
        interaction: nextcord.Interaction,
        member: nextcord.Member = SlashOption(description="The user"),
    ):
        settings = await self._gate_manager(interaction)
        if settings is None:
            return
        user = await self.bot.db.users.find_one({"discord_id": member.id})
        if user is None:
            await interaction.response.send_message(
                f"{member.mention} has no key.", ephemeral=True
            )
            return
        embed = nextcord.Embed(
            title=f"BiomeBeacon — {member.display_name}",
            color=0x46C97A if user.get("active") else 0xE5484D,
        )
        embed.add_field(
            name="Status", value="active" if user.get("active") else "revoked", inline=True
        )
        embed.add_field(name="Key", value=f"`{user.get('key_prefix', '?')}…`", inline=True)
        embed.add_field(name="Last seen", value=discord_ts(user.get("last_seen")), inline=True)
        macro = user.get("macro_version") or "—"
        if user.get("instances"):
            macro += f" ({user['instances']} instances)"
        embed.add_field(name="Macro", value=macro, inline=True)
        embed.add_field(
            name="Channel",
            value=f"<#{user['channel_id']}>" if user.get("channel_id") else "—",
            inline=True,
        )
        embed.add_field(
            name="Private server",
            value=user.get("private_server_link") or "—",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------------------------------------------------------- /myserver

    @nextcord.slash_command(
        name="myserver", description="Update your own Roblox private server link"
    )
    async def myserver(
        self,
        interaction: nextcord.Interaction,
        link: str = SlashOption(description="Your private server link"),
    ):
        db = self.bot.db
        user = await db.users.find_one({"discord_id": interaction.user.id})
        if user is None:
            await interaction.response.send_message(
                "You don't have a BiomeBeacon key — ask a key manager for `/key create`.",
                ephemeral=True,
            )
            return
        if not valid_private_server_link(link):
            await interaction.response.send_message(
                "That doesn't look like a Roblox private server link.", ephemeral=True
            )
            return
        await db.users.update_one(
            {"discord_id": interaction.user.id},
            {"$set": {"private_server_link": link.strip()}},
        )
        await interaction.response.send_message(
            "Private server link updated. It will be used in your next biome alerts.",
            ephemeral=True,
        )
