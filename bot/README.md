# BiomeBeacon — Discord bot

nextcord bot each community self-hosts alongside the server (same MongoDB). It is
the human-friendly admin surface: keys, channels, webhooks, inactivity.

## Commands

| Command | Who | What |
|---|---|---|
| `/setup mode` | admin | single channel / per-biome / per-user dispatch (creates webhooks/categories) |
| `/setup biomechannel` | admin | map a biome to a channel (per-biome mode) |
| `/setup roles` | admin | set admin + key-manager + member roles (member role is granted on key creation, required for per-user mode) |
| `/setup syncchannels` | admin | backfill: give the member role read access to all existing per-user channels |
| `/setup inactivity` | admin | auto-purge after N quiet days |
| `/setup show` | admin | current configuration |
| `/admintoken create` | Discord Administrator | dashboard token (shown once) |
| `/key create member: private_server:` | key manager | create key (+channel/webhook in per-user mode), DM credentials |
| `/key revoke / regenerate / info` | key manager | lifecycle + status |
| `/inactive list / purge` | key manager | see / remove users past the inactivity limit |
| `/myserver link:` | any key holder | update own private server link |

## Run

```bash
cp .env.example .env      # DISCORD_TOKEN, GUILD_ID, MONGODB_URI, PUBLIC_SERVER_URL
pip install -r requirements.txt
python -m biomebeacon_bot
```

Bot invite needs scopes `bot` + `applications.commands` and permissions
**Manage Channels**, **Manage Webhooks**, **Send Messages**, and **Manage Roles**
(to grant/remove the member access role in per-user mode — keep the bot's own role
above the member role in the hierarchy). No privileged intents. Slash commands are
registered guild-scoped (`GUILD_ID`), so they appear instantly.

## Notes

- Key hashing is byte-identical to the server (parity vector in
  [docs/DATA_MODEL.md](../docs/DATA_MODEL.md), asserted by tests on both sides).
- The inactivity loop runs every 6h; `last_seen` is refreshed by any authenticated
  macro request (heartbeats every 5 min while the macro is open).

## Tests

```bash
python -m pytest bot/tests       # from the repo root
```
