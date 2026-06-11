"""Permission gates. Pure functions over member-like objects so they are unit-testable."""

from __future__ import annotations


def _role_ids(member) -> set[int]:
    return {role.id for role in getattr(member, "roles", [])}


def is_admin(member, settings: dict) -> bool:
    """Discord Administrator permission, or the configured admin role."""
    if getattr(member.guild_permissions, "administrator", False):
        return True
    admin_role = settings.get("admin_role_id")
    return admin_role is not None and admin_role in _role_ids(member)


def is_key_manager(member, settings: dict) -> bool:
    """Admins always qualify; otherwise the configured key-manager role."""
    if is_admin(member, settings):
        return True
    manager_role = settings.get("key_manager_role_id")
    return manager_role is not None and manager_role in _role_ids(member)
