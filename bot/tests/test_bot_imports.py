"""Importing the cogs executes nextcord's slash-command decorators, which
validates option signatures without needing a Discord connection."""


def test_cogs_import_cleanly():
    from biomebeacon_bot.cogs.inactivity import InactivityCog
    from biomebeacon_bot.cogs.keys import KeysCog
    from biomebeacon_bot.cogs.setup import SetupCog

    assert SetupCog and KeysCog and InactivityCog
