"""Discord channel/webhook provisioning, shared by /key commands and the
inactivity purge task."""

from __future__ import annotations

import logging
import re

import nextcord

log = logging.getLogger(__name__)

WEBHOOK_NAME = "BiomeBeacon"


def channel_name_for(member: nextcord.Member) -> str:
    base = re.sub(r"[^a-z0-9-]", "-", (member.display_name or member.name).lower())
    base = re.sub(r"-+", "-", base).strip("-") or str(member.id)
    return f"biome-{base}"[:90]


async def create_user_channel(
    guild: nextcord.Guild, member: nextcord.Member, category_id: int | None
) -> tuple[int, str]:
    """Creates the hunter's private channel + webhook. Returns (channel_id, webhook_url)."""
    category = guild.get_channel(category_id) if category_id else None
    if category is not None and not isinstance(category, nextcord.CategoryChannel):
        category = None
    overwrites = {
        guild.default_role: nextcord.PermissionOverwrite(view_channel=False),
        member: nextcord.PermissionOverwrite(view_channel=True, read_message_history=True),
        guild.me: nextcord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_webhooks=True
        ),
    }
    channel = await guild.create_text_channel(
        name=channel_name_for(member),
        category=category,
        overwrites=overwrites,
        reason=f"BiomeBeacon channel for {member} ({member.id})",
    )
    webhook = await channel.create_webhook(name=WEBHOOK_NAME)
    return channel.id, webhook.url


async def delete_user_channel(guild: nextcord.Guild, channel_id: int | None) -> bool:
    """Deletes the hunter's channel (webhooks die with it). Returns True if deleted."""
    if not channel_id:
        return False
    channel = guild.get_channel(channel_id)
    if channel is None:
        return False
    try:
        await channel.delete(reason="BiomeBeacon: access removed")
        return True
    except nextcord.HTTPException as exc:
        log.warning("could not delete channel %s: %s", channel_id, exc)
        return False


async def create_channel_webhook(channel: nextcord.TextChannel) -> str:
    """Reuses an existing BiomeBeacon webhook on the channel, or creates one."""
    for webhook in await channel.webhooks():
        if webhook.name == WEBHOOK_NAME and webhook.url:
            return webhook.url
    webhook = await channel.create_webhook(name=WEBHOOK_NAME)
    return webhook.url
