# Data Model (MongoDB)

This document is the **contract between the server and the bot**. Both processes read and
write the same MongoDB database but share no code — if you change anything here, update
both components and their tests.

Database name: `biomebeacon` (configurable via `DB_NAME`).

## API keys and hashing (shared contract)

- User keys: `bb_` + `secrets.token_urlsafe(32)` (46 chars total).
- Admin tokens: `bba_` + `secrets.token_urlsafe(32)`.
- Keys/tokens are shown **once** at creation and never stored in plaintext.
- Stored hash: `hashlib.sha256(key.encode("utf-8")).hexdigest()` of the **full** key string
  (prefix included), lowercase hex.

**Parity test vector** (asserted by both `server/tests` and `bot/tests`):

```
key  = "bb_unittest-key-000"
hash = "114198bf7bbb3c482241b2662b531f31891fc92f332308ea433b38a7e113a0bd"
```

## Collection: `settings` (singleton)

One document with `_id: "settings"`. Created with defaults on first run of either process.

| Field | Type | Default | Notes |
|---|---|---|---|
| `_id` | str | `"settings"` | singleton key |
| `guild_id` | int \| null | null | set by the bot on `/setup` |
| `dispatch_mode` | str | `"single_channel"` | `single_channel` \| `per_biome_channels` \| `per_user_channels` |
| `relay` | bool | `true` | true: macro posts events to the server, server dispatches webhooks. false: macro receives its webhook URL and posts directly (**only valid with `per_user_channels`**) |
| `category_id` | int \| null | null | Discord category for auto-created user channels |
| `single_channel_webhook` | str \| null | null | primary webhook URL for `single_channel` mode |
| `single_channel_webhooks` | str[] | `[]` | extra webhooks for the **same** channel; dispatcher round-robins across all of them (Discord rate-limits per webhook, so this scales single-channel throughput for large communities) |
| `single_channel_webhook_broken` | bool | `false` | set by dispatcher on 404/410 |
| `admin_role_id` | int \| null | null | role allowed to manage everything |
| `key_manager_role_id` | int \| null | null | role allowed to create/revoke keys |
| `inactivity_days` | int | `3` | purge threshold based on `users.last_seen` |
| `inactivity_enabled` | bool | `false` | daily purge task on/off |
| `min_macro_version` | str | `"0.0.0"` | server rejects older macros (`409`) |
| `place_ids` | int[] | `[15532962292]` | Roblox place ids treated as Sol's RNG |
| `heartbeat_interval` | int | `300` | seconds, sent to the macro via config |

## Collection: `biomes`

Seeded by the server on first run. Admins may add event biomes at any time — the macro
receives the list via `GET /me/config`, so no macro update is needed.

| Field | Type | Notes |
|---|---|---|
| `name` | str | **unique**, uppercase, exactly as it appears in `largeImage.hoverText` (e.g. `"SAND STORM"`) |
| `display` | str | human-readable (e.g. `"Sand Storm"`) |
| `color` | int | embed color (e.g. `0x8A2BE2`) |
| `image_url` | str \| null | embed thumbnail |
| `notify` | bool | false = audit only, no webhook (default for `NORMAL`) |
| `ping_everyone` | bool | mention `@everyone` on `started` (takes precedence over `ping_role_id`) |
| `ping_role_id` | int \| null | role mentioned on `started` |
| `channel_id` | int \| null | `per_biome_channels` mode |
| `webhook_url` | str \| null | `per_biome_channels` mode |
| `webhook_broken` | bool | set by dispatcher on 404/410 |

Seed list: `NORMAL` (notify=false), `WINDY`, `RAINY`, `SNOWY`, `SAND STORM`, `HELL`,
`STARFALL`, `CORRUPTION`, `AURORA`, `EGGLAND`, `NULL`, `GLITCHED`, `DREAMSPACE`,
`HEAVEN`, `CYBERSPACE`, `SINGULARITY`. Colors and `image_url` thumbnails follow the
Coteab macro's `biomes_data.json` so embeds look consistent across community tools.
`GLITCHED`, `DREAMSPACE` and `CYBERSPACE` seed with `ping_everyone=true`; admins can
turn it off per biome in the dashboard.

## Collection: `users`

Created by the bot (`/key create`). The server only updates `last_seen`, `last_event_at`,
`macro_version`, `roblox_user_ids` and `private_server_link`.

| Field | Type | Notes |
|---|---|---|
| `discord_id` | int | **unique** |
| `discord_name` | str | display copy, refreshed by the bot |
| `key_hash` | str | **unique**, sha256 hex (see contract above) |
| `key_prefix` | str | first 8 chars of the key, for identification in UIs |
| `private_server_link` | str \| null | Roblox private server link |
| `channel_id` | int \| null | `per_user_channels` mode |
| `webhook_url` | str \| null | `per_user_channels` mode |
| `webhook_broken` | bool | set by dispatcher on 404/410 |
| `active` | bool | false = key rejected (revoked / inactivity purge) |
| `created_at` | datetime (UTC) | |
| `created_by` | int | Discord id of the admin who created it |
| `last_seen` | datetime \| null | any authenticated macro request updates this |
| `last_event_at` | datetime \| null | last biome event |
| `macro_version` | str \| null | reported via heartbeat |
| `roblox_user_ids` | int[] | accounts seen in events (multi-instance) |

## Collection: `events` (rare-biome log)

Written by the server only. TTL index on `server_ts` (30 days). **Only events for
biomes with `ping_everyone=true` are persisted** — for large (1000+ user)
communities the flood of common transitions would dominate writes and storage for
near-zero value. Mid-tier biomes are still dispatched as webhooks, just not stored,
so this collection is effectively the rare-biome audit log (and the source of the
"Lasted X min" duration, which is therefore only computed for `@everyone` biomes).

| Field | Type |
|---|---|
| `user_id` | int (discord_id) |
| `biome` | str |
| `type` | `"started"` \| `"ended"` |
| `client_ts` | datetime (UTC) |
| `server_ts` | datetime (UTC) |
| `private_server_link` | str \| null |
| `roblox_user_id` | int \| null |
| `macro_version` | str \| null |
| `dispatched` | bool |

## Collection: `admin_tokens`

Created by the bot (`/admintoken create`). The env var `ADMIN_BOOTSTRAP_TOKEN` (server)
is accepted as an additional admin token without a database entry.

| Field | Type |
|---|---|
| `token_hash` | str (**unique**, sha256 hex) |
| `token_prefix` | str (first 9 chars) |
| `label` | str |
| `discord_id` | int (creator) |
| `created_at` | datetime (UTC) |
| `active` | bool |

## Indexes

| Collection | Index | Options |
|---|---|---|
| `users` | `key_hash` | unique |
| `users` | `discord_id` | unique |
| `biomes` | `name` | unique |
| `events` | `server_ts` | `expireAfterSeconds=2592000` (30d) |
| `events` | `(user_id, server_ts desc)` | |
| `admin_tokens` | `token_hash` | unique |
