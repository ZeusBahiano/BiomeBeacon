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
| [`macro/`](macro/) | Open-source Windows app (HTML UI in a native WebView2 window via pywebview, styled after the game's menus). Tails Roblox logs, detects biome changes, sends events. Distributed as a PyInstaller `.exe`. | Each user |
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
Any questions or issues dm me on discord or make a PR or open an issue (@zeusbahiano)

## Credits

- UI design and biome colors/artwork adapted from
  [Coteab Macro](https://github.com/xVapure/Noteab-Macro) (Copyright 2025 Noteab,
  [Apache License 2.0](LICENSES/Apache-2.0.txt)) — see
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for what was used and modified.
  BiomeBeacon is intentionally **detection-only** — for everything else a Sol's RNG
  macro can do (auto-fish, auto crafting and more), use Coteab Macro.
  They run great side by side.
- Parts of this codebase were written with AI assistance (Claude).
- The bundled [Sarpanch](https://fonts.google.com/specimen/Sarpanch) font is used
  under the SIL Open Font License.

License: [MIT](LICENSE), with third-party components under their own terms —
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
