"""/setup — guild configuration, and /admintoken for dashboard access."""

from __future__ import annotations

import logging

import nextcord
from nextcord import SlashOption
from nextcord.ext import commands

from ..db import get_settings, update_settings, utcnow
from ..keys import generate_admin_token
from ..permissions import is_admin
from ..provisioning import create_channel_webhook

log = logging.getLogger(__name__)

MODE_CHOICES = {
    "Single channel (all alerts in one channel)": "single_channel",
    "Per-biome channels": "per_biome_channels",
    "Per-user channels (auto-created)": "per_user_channels",
}


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _gate_admin(self, interaction: nextcord.Interaction) -> dict | None:
        settings = await get_settings(self.bot.db)
        if not is_admin(interaction.user, settings):
            await interaction.response.send_message(
                "You need **Administrator** (or the configured admin role) for this.",
                ephemeral=True,
            )
            return None
        return settings

    # ------------------------------------------------------------------ /setup

    @nextcord.slash_command(name="setup", description="Configure BiomeBeacon")
    async def setup_group(self, interaction: nextcord.Interaction):
        pass

    @setup_group.subcommand(name="mode", description="Choose how biome alerts are delivered")
    async def setup_mode(
        self,
        interaction: nextcord.Interaction,
        mode: str = SlashOption(description="Dispatch mode", choices=MODE_CHOICES),
        channel: nextcord.abc.GuildChannel = SlashOption(
            description="Alert channel (single-channel mode)",
            required=False,
            channel_types=[nextcord.ChannelType.text],
        ),
        category: nextcord.abc.GuildChannel = SlashOption(
            description="Category for auto-created user channels (per-user mode)",
            required=False,
            channel_types=[nextcord.ChannelType.category],
        ),
    ):
        settings = await self._gate_admin(interaction)
        if settings is None:
            return
        await interaction.response.defer(ephemeral=True)
        updates: dict = {"dispatch_mode": mode, "guild_id": interaction.guild.id}
        notes: list[str] = []

        if mode == "single_channel":
            if channel is None:
                await interaction.followup.send("Pass `channel:` for single-channel mode.")
                return
            try:
                webhook_url = await create_channel_webhook(channel)
            except nextcord.Forbidden:
                await interaction.followup.send(
                    "I need **Manage Webhooks** on that channel."
                )
                return
            updates |= {
                "single_channel_webhook": webhook_url,
                "single_channel_webhook_broken": False,
            }
            notes.append(f"Alerts will go to {channel.mention}.")
        elif mode == "per_user_channels":
            if category is None:
                await interaction.followup.send("Pass `category:` for per-user mode.")
                return
            updates["category_id"] = category.id
            notes.append(
                f"`/key create` will now auto-create channels under **{category.name}**."
            )
        else:  # per_biome_channels
            notes.append(
                "Now map each biome with `/setup biomechannel` — unmapped biomes are not sent."
            )

        # Direct-webhook flow only makes sense with per-user channels.
        if mode != "per_user_channels" and not settings.get("relay", True):
            updates["relay"] = True
            notes.append("`relay` was re-enabled (direct mode requires per-user channels).")

        await update_settings(self.bot.db, updates)
        await interaction.followup.send(
            f"Dispatch mode set to **{mode}**.\n" + "\n".join(notes)
        )

    @setup_group.subcommand(name="roles", description="Set admin and key-manager roles")
    async def setup_roles(
        self,
        interaction: nextcord.Interaction,
        key_manager: nextcord.Role = SlashOption(
            description="Role allowed to create/revoke keys", required=False
        ),
        admin: nextcord.Role = SlashOption(
            description="Role with full BiomeBeacon admin", required=False
        ),
    ):
        if await self._gate_admin(interaction) is None:
            return
        updates: dict = {}
        if key_manager is not None:
            updates["key_manager_role_id"] = key_manager.id
        if admin is not None:
            updates["admin_role_id"] = admin.id
        if not updates:
            await interaction.response.send_message(
                "Pass `key_manager:` and/or `admin:`.", ephemeral=True
            )
            return
        await update_settings(self.bot.db, updates)
        await interaction.response.send_message("Roles updated.", ephemeral=True)

    @setup_group.subcommand(
        name="inactivity", description="Auto-remove hunters whose macro went quiet"
    )
    async def setup_inactivity(
        self,
        interaction: nextcord.Interaction,
        enabled: bool = SlashOption(description="Enable the daily purge"),
        days: int = SlashOption(
            description="Days without macro activity before removal (default 3)",
            required=False,
            min_value=1,
            max_value=90,
        ),
    ):
        if await self._gate_admin(interaction) is None:
            return
        updates: dict = {"inactivity_enabled": enabled}
        if days is not None:
            updates["inactivity_days"] = days
        await update_settings(self.bot.db, updates)
        await interaction.response.send_message(
            f"Inactivity purge **{'enabled' if enabled else 'disabled'}**"
            + (f" ({days} days)." if days is not None else "."),
            ephemeral=True,
        )

    @setup_group.subcommand(
        name="biomechannel", description="Map a biome to a channel (per-biome mode)"
    )
    async def setup_biomechannel(
        self,
        interaction: nextcord.Interaction,
        biome: str = SlashOption(description="Biome name, e.g. GLITCHED"),
        channel: nextcord.abc.GuildChannel = SlashOption(
            description="Channel for this biome's alerts",
            channel_types=[nextcord.ChannelType.text],
        ),
    ):
        if await self._gate_admin(interaction) is None:
            return
        await interaction.response.defer(ephemeral=True)
        name = biome.strip().upper()
        doc = await self.bot.db.biomes.find_one({"name": name})
        if doc is None:
            await interaction.followup.send(
                f"Unknown biome `{name}` — add it on the dashboard first."
            )
            return
        try:
            webhook_url = await create_channel_webhook(channel)
        except nextcord.Forbidden:
            await interaction.followup.send("I need **Manage Webhooks** on that channel.")
            return
        await self.bot.db.biomes.update_one(
            {"name": name},
            {"$set": {
                "channel_id": channel.id,
                "webhook_url": webhook_url,
                "webhook_broken": False,
            }},
        )
        await update_settings(self.bot.db, {})  # bump updated_at so macros refresh
        await interaction.followup.send(f"**{name}** alerts → {channel.mention}")

    @setup_group.subcommand(name="show", description="Show the current configuration")
    async def setup_show(self, interaction: nextcord.Interaction):
        settings = await self._gate_admin(interaction)
        if settings is None:
            return
        biome_hooks = await self.bot.db.biomes.count_documents(
            {"webhook_url": {"$nin": [None, ""]}}
        )
        embed = nextcord.Embed(title="BiomeBeacon configuration", color=0x7C3AED)
        embed.add_field(name="Dispatch mode", value=settings["dispatch_mode"], inline=True)
        embed.add_field(
            name="Webhook flow",
            value="relay (via server)" if settings["relay"] else "direct (macro posts)",
            inline=True,
        )
        embed.add_field(
            name="Single channel webhook",
            value=(
                "⚠️ broken"
                if settings.get("single_channel_webhook_broken")
                else ("set" if settings.get("single_channel_webhook") else "—")
            ),
            inline=True,
        )
        embed.add_field(
            name="User channel category",
            value=f"<#{settings['category_id']}>" if settings.get("category_id") else "—",
            inline=True,
        )
        embed.add_field(name="Biome channels mapped", value=str(biome_hooks), inline=True)
        embed.add_field(
            name="Inactivity purge",
            value=(
                f"on ({settings['inactivity_days']}d)"
                if settings.get("inactivity_enabled")
                else "off"
            ),
            inline=True,
        )
        admin_role = settings.get("admin_role_id")
        manager_role = settings.get("key_manager_role_id")
        embed.add_field(
            name="Roles",
            value=(
                f"admin: {f'<@&{admin_role}>' if admin_role else '—'}\n"
                f"key manager: {f'<@&{manager_role}>' if manager_role else '—'}"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------- /admintoken

    @nextcord.slash_command(
        name="admintoken", description="Manage dashboard admin tokens"
    )
    async def admintoken_group(self, interaction: nextcord.Interaction):
        pass

    @admintoken_group.subcommand(name="create", description="Create a dashboard admin token")
    async def admintoken_create(
        self,
        interaction: nextcord.Interaction,
        label: str = SlashOption(description="Who/what this token is for"),
    ):
        # Stricter than the role gate: only true Discord administrators.
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Only members with **Administrator** can create dashboard tokens.",
                ephemeral=True,
            )
            return
        token, token_hash, token_prefix = generate_admin_token()
        await self.bot.db.admin_tokens.insert_one(
            {
                "token_hash": token_hash,
                "token_prefix": token_prefix,
                "label": label,
                "discord_id": interaction.user.id,
                "created_at": utcnow(),
                "active": True,
            }
        )
        await interaction.response.send_message(
            f"Dashboard token for **{label}** (shown once, keep it secret):\n||`{token}`||\n"
            f"Sign in at {self.bot.public_server_url}/admin",
            ephemeral=True,
        )
