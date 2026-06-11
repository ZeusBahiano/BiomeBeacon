from types import SimpleNamespace

from biomebeacon_bot.permissions import is_admin, is_key_manager


def member(administrator=False, roles=()):
    return SimpleNamespace(
        guild_permissions=SimpleNamespace(administrator=administrator),
        roles=[SimpleNamespace(id=role_id) for role_id in roles],
    )


SETTINGS = {"admin_role_id": 100, "key_manager_role_id": 200}
UNCONFIGURED = {"admin_role_id": None, "key_manager_role_id": None}


def test_discord_administrator_is_both():
    m = member(administrator=True)
    assert is_admin(m, SETTINGS)
    assert is_key_manager(m, SETTINGS)


def test_admin_role_is_both():
    m = member(roles=[100])
    assert is_admin(m, SETTINGS)
    assert is_key_manager(m, SETTINGS)


def test_key_manager_role_is_manager_only():
    m = member(roles=[200])
    assert not is_admin(m, SETTINGS)
    assert is_key_manager(m, SETTINGS)


def test_plain_member_is_neither():
    m = member(roles=[300])
    assert not is_admin(m, SETTINGS)
    assert not is_key_manager(m, SETTINGS)


def test_unconfigured_roles_grant_nothing():
    m = member(roles=[100, 200])
    assert not is_admin(m, UNCONFIGURED)
    assert not is_key_manager(m, UNCONFIGURED)
