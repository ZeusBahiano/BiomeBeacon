# BiomeBeacon

Biome detection and alerting ecosystem for **Sol's RNG** (Roblox) biome-hunting
communities. When a rare biome (Glitched, Dreamspace, …) starts in a user's private
server, everyone in the community's Discord gets pinged with the link to join.

## How it works

```
Roblox client logs ──> [ Macro (.exe) ] ──events──> [ Server ] ──webhooks──> Discord channels
                          ▲    user key                 ▲  MongoDB
                          │                             │
                          └──── key + config ────  [ Discord Bot ]
                                                   /key create, channels,
                                                   inactivity purge, /setup
```

The **macro is universal**: any community can point it at their own server with their own
key. Each community self-hosts the **server** and the **bot** (they share a MongoDB
database — see [docs/DATA_MODEL.md](docs/DATA_MODEL.md)).

## Components

| Component | What it is | Who runs it |
|---|---|---|
| [`macro/`](macro/) | Open-source Windows app (customtkinter). Tails Roblox logs, detects biome changes, sends events. Distributed as a PyInstaller `.exe`. | Each user |
| [`server/`](server/) | aiohttp REST API + admin dashboard + webhook dispatcher (MongoDB). | The community |
| [`bot/`](bot/) | nextcord Discord bot: creates keys, auto-provisions channels/webhooks, purges inactive users. | The community |

## Documentation

- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) — MongoDB collections (server ↔ bot contract)
- [docs/API.md](docs/API.md) — REST API contract (macro ↔ server, admin ↔ server)
- [docs/SELF_HOSTING.md](docs/SELF_HOSTING.md) — hosting guide for communities

## Development

Single venv at the repo root works for all components:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r macro/requirements.txt -r server/requirements.txt -r bot/requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest macro server bot
```

License: [MIT](LICENSE).
