# REST API (server)

Base path: `/api/v1`. All bodies are JSON. Errors return `{"error": "<message>"}` with an
appropriate 4xx/5xx status.

## Authentication

| Caller | Header | Credential |
|---|---|---|
| Macro | `Authorization: Bearer bb_…` | user key (created by the bot) |
| Admin (dashboard / scripts) | `Authorization: Bearer bba_…` | admin token (`/admintoken create` or `ADMIN_BOOTSTRAP_TOKEN`) |

- Unknown/revoked credentials → `401`.
- A user key on an `/admin/*` route → `403`.
- Per-key rate limit: 30 requests/min → `429` with `{"error": "rate limited", "retry_after": <s>}`.
- If the macro version reported is older than `settings.min_macro_version` → `409`
  `{"error": "macro update required", "min_version": "x.y.z"}`.

## Public

### `GET /health`
No auth. Used by the macro's "Test connection".
```json
{"name": "BiomeBeacon Server", "version": "0.1.0", "server_name": "My Community"}
```

## Macro endpoints (user key)

### `GET /api/v1/me/config`
Everything the macro needs. `dispatch.webhook_url` is present **only** when
`relay=false` (direct mode, `per_user_channels` only).
```json
{
  "user": {"discord_id": 123, "discord_name": "lucas", "private_server_link": "https://..."},
  "dispatch": {"relay": true, "webhook_url": null},
  "biomes": [
    {"name": "GLITCHED", "display": "Glitched", "color": 8388863,
     "image_url": null, "notify": true, "ping_role_id": 456}
  ],
  "place_ids": [15532962292],
  "heartbeat_interval": 300,
  "min_macro_version": "0.0.0",
  "server_name": "My Community"
}
```

### `POST /api/v1/events`
Batch of detected transitions (max 20). Unknown biome names → `422`.
```json
{"events": [
  {"biome": "GLITCHED", "type": "started", "client_ts": "2026-06-11T12:00:00Z",
   "roblox_user_id": 1420234927}
]}
```
Response: `{"accepted": 1, "dispatched": 1}` — `dispatched` counts webhook deliveries
queued (relay mode; biomes with `notify=false` are audited but not dispatched).
Side effects: audit insert, `users.last_seen`/`last_event_at`/`roblox_user_ids` update.

### `POST /api/v1/heartbeat`
```json
{"macro_version": "0.1.0", "instances": 3}
```
Response: `{"ok": true, "config_stale": false}` — `config_stale=true` hints the macro to
re-fetch `/me/config` (settings changed since the macro's last fetch).

### `PATCH /api/v1/me/private-server`
The only user-editable field, as designed. Link must match a Roblox private-server URL
(`roblox.com/games/<id>?...privateServerLinkCode=...` or `roblox.com/share?code=...&type=Server`),
otherwise `422`.
```json
{"link": "https://www.roblox.com/share?code=ab12cd34ef&type=Server"}
```

## Admin endpoints (admin token)

| Method & path | Purpose |
|---|---|
| `GET /api/v1/admin/stats` | totals: users, active users, events 24h, broken webhooks |
| `GET /api/v1/admin/users?active=true\|false` | list users (no hashes) |
| `GET /api/v1/admin/users/{discord_id}` | user detail |
| `PATCH /api/v1/admin/users/{discord_id}` | `{active, private_server_link}` |
| `POST /api/v1/admin/users/{discord_id}/regenerate-key` | returns `{"key": "bb_…"}` **once** |
| `DELETE /api/v1/admin/users/{discord_id}` | hard delete (bot `/key revoke` is preferred — it also cleans Discord channels) |
| `GET /api/v1/admin/settings` | settings document |
| `PATCH /api/v1/admin/settings` | partial update (validated; `relay=false` requires `per_user_channels`) |
| `GET /api/v1/admin/biomes` | full biome list (incl. webhooks) |
| `PUT /api/v1/admin/biomes/{name}` | create/update biome |
| `DELETE /api/v1/admin/biomes/{name}` | remove biome |
| `GET /api/v1/admin/events?limit=50&user=&biome=` | audit log |
| `POST /api/v1/admin/test-webhook` | `{"target": "single" \| "biome:GLITCHED" \| "user:123"}` → sends a test embed |

Note: **user creation lives in the bot** (`/key create`) because it provisions Discord
channels/webhooks. The dashboard manages everything else.

## Dashboard

`GET /admin` serves a static single-page dashboard. Login = paste an admin token
(stored in the browser, sent as Bearer on every call to the endpoints above).
