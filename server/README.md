# BiomeBeacon — server

aiohttp service each community self-hosts: authenticates macro keys, validates and
audits biome events, dispatches Discord webhooks (single channel / per-biome /
per-user modes) and serves the admin dashboard at `/admin`.

## Run

```bash
cp .env.example .env      # MONGODB_URI, SERVER_NAME, ADMIN_BOOTSTRAP_TOKEN, ...
pip install -r requirements.txt
python -m biomebeacon_server
```

Or `docker compose up -d` from `../deploy` (includes MongoDB). Full guide:
[docs/SELF_HOSTING.md](../docs/SELF_HOSTING.md).

## Environment

| Var | Default | Purpose |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | Atlas M0 free tier works |
| `DB_NAME` | `biomebeacon` | shared with the bot |
| `HOST` / `PORT` | `0.0.0.0` / `8400` | bind address |
| `SERVER_NAME` | `BiomeBeacon` | shown in the macro + webhook username |
| `ADMIN_BOOTSTRAP_TOKEN` | _empty_ | first dashboard login (then `/admintoken create`) |
| `LOG_LEVEL` | `INFO` | |

## API

Contract in [docs/API.md](../docs/API.md); data shapes in
[docs/DATA_MODEL.md](../docs/DATA_MODEL.md). Highlights:

- user keys are sha256-hashed at rest; rate limit 30 req/min per key
- `relay=false` (macro posts webhooks itself) is only honored with per-user
  channels, so shared webhooks can never leak
- broken webhooks (HTTP 401/404/410) are flagged and surface on the dashboard

## Tests

```bash
python -m pytest server/tests        # from the repo root (mongomock, no Mongo needed)
```
