# Self-hosting guide (for community admins)

Each Discord community hosts **two processes** — the server (REST API + dashboard +
webhook dispatcher) and the bot — sharing one MongoDB database. The macro is the same
for everyone; your users just point it at *your* server URL with *their* key.

```
[user PCs: BiomeBeacon.exe] ──HTTPS──> [your server :8400] ──webhooks──> [your Discord]
                                            │
                                        [MongoDB]
                                            │
                                       [your bot]
```

## 1. Prerequisites

- A place to run two small processes 24/7: any VPS, Railway, Render, a spare PC…
- **MongoDB**: easiest is a free [MongoDB Atlas M0 cluster](https://www.mongodb.com/cloud/atlas)
  (no card needed) — copy its connection string. Self-hosted Mongo works too
  (docker-compose below includes one).
- A **Discord application** with a bot:
  1. [discord.com/developers/applications](https://discord.com/developers/applications) → New Application → Bot → copy the **token**.
  2. No privileged intents are needed.
  3. Invite it to your server with scopes `bot` + `applications.commands` and permissions
     **Manage Channels**, **Manage Webhooks**, **Send Messages**
     (permissions integer `537160720` works).
- Your **guild id** (Discord server id, with developer mode on: right-click server → Copy ID).

## 2A. Run with docker-compose (includes MongoDB)

```bash
cd deploy
cp .env.example .env     # fill DISCORD_TOKEN, GUILD_ID, SERVER_NAME, ADMIN_BOOTSTRAP_TOKEN, PUBLIC_SERVER_URL
docker compose up -d
```

Done — server on port 8400, bot online, Mongo persisted in a volume.

## 2B. Run manually (e.g. with Atlas)

```bash
# server
cd server
cp .env.example .env     # set MONGODB_URI to your Atlas string, SERVER_NAME, ADMIN_BOOTSTRAP_TOKEN
pip install -r requirements.txt
python -m biomebeacon_server

# bot (second terminal)
cd bot
cp .env.example .env     # set DISCORD_TOKEN, GUILD_ID, same MONGODB_URI, PUBLIC_SERVER_URL
pip install -r requirements.txt
python -m biomebeacon_bot
```

`PUBLIC_SERVER_URL` is the address users will reach your server at (it is included in
the key DM). Put the server behind HTTPS for anything public — a Caddy/nginx reverse
proxy or your PaaS's built-in TLS.

## 3. First-time setup (in Discord)

1. `/setup mode` — pick how alerts are delivered:
   - **Single channel**: everything into one channel (pass `channel:`).
   - **Per-biome channels**: map each biome with `/setup biomechannel biome: channel:`.
   - **Per-user channels**: pass `category:`; `/key create` then auto-creates a private
     channel + webhook per user.
2. `/setup roles key_manager: admin:` — who may create keys / administrate.
3. `/setup inactivity enabled: true days: 3` — auto-remove users whose macro went
   quiet (deletes their channel, frees the Discord channel limit).
4. `/admintoken create label: yourname` — token for the web dashboard at
   `https://your-server/admin` (or sign in once with `ADMIN_BOOTSTRAP_TOKEN` from .env).
5. On the dashboard → **Biomes**: set ping roles (e.g. @Glitched), colors, images;
   toggle `notify` per biome. New event biomes can be added any time — macros pick
   them up automatically, no .exe update needed.
6. `/key create member:@someone private_server:<link>` — the user receives the
   server URL + key via DM and pastes both into the macro's Settings.

## 4. Day-2 operations

| Need | Where |
|---|---|
| Revoke someone / regenerate a key | `/key revoke`, `/key regenerate` (or dashboard → Users) |
| See who's inactive | `/inactive list`, purge now with `/inactive purge` |
| User changed their private server | they run `/myserver link:` or edit it in the macro |
| Check a user's macro status | `/key info member:` |
| Test a webhook | dashboard → Settings → *Send test webhook* |
| Broken webhook (channel deleted) | dashboard Overview lists it; re-run `/setup mode` or `/setup biomechannel` |
| Force macros to update | dashboard → Settings → `min_macro_version` (older macros get HTTP 409) |

## 5. Relay vs direct webhooks

Default is **relay**: macros send events to your server and *the server* posts the
webhooks — webhook URLs never leave your infrastructure, and everything is rate-limited
and audited centrally. If you prefer macros posting straight to Discord (lower latency,
less server traffic), set `relay = false` — only allowed with **per-user channels**, so
a user can only ever see (and leak) their own webhook.

## 6. Security model in one paragraph

Keys (`bb_…`) and admin tokens (`bba_…`) are stored **hashed** (sha256) — a database
leak does not leak credentials. A user key can only read its own config, post its own
events, and edit its own private-server link. Admin endpoints require an admin token.
Per-key rate limiting (30 req/min) and a biome whitelist blunt spam/fake reports; the
events audit log (30-day TTL) lets you investigate abuse.
