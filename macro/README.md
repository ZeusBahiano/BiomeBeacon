# BiomeBeacon — macro

Windows app that detects Sol's RNG biome changes by reading the **Roblox client
logs** (no game injection, no input automation — log files only) and alerts your
community's Discord through their BiomeBeacon server.

## For users

1. Get your **Server URL** and **API key** from your community (an admin runs
   `/key create` for you — both arrive via DM).
2. Run `BiomeBeacon.exe`, open **Settings**, paste both, hit *Save & test connection*.
3. Set your private server link (Settings or `/myserver` in Discord).
4. Play. When a biome starts/ends on any of your Roblox instances (multi-account
   works out of the box), your community gets the alert with your join link.

## How detection works

The game updates Discord Rich Presence through lines the Roblox client writes to
`%LOCALAPPDATA%\Roblox\logs`:

```
... [BloxstrapRPC] {"command":"SetRichPresence","data":{...,
    "smallImage":{"hoverText":"Sol's RNG",...},
    "largeImage":{"hoverText":"RAINY",...}}}
```

`largeImage.hoverText` is the current biome; a change means the previous biome
ended and a new one started. One log file per Roblox instance gives multi-account
support. The biome list itself comes from your community's server, so new event
biomes need no app update.

## For developers

```powershell
# from the repo root
.venv\Scripts\python -m pip install -r macro/requirements.txt -r requirements-dev.txt
$env:PYTHONPATH = "macro"
.venv\Scripts\python -m biomebeacon          # run from source
.venv\Scripts\python -m pytest macro/tests   # tests
```

Test without Roblox or Discord:

```powershell
python macro/tools/webhook_sink.py           # fake Discord webhook (prints payloads)
python macro/tools/sim_logs.py --biome GLITCHED --hold 30   # fake Roblox logs
# point Settings -> Advanced -> log directory override at the printed folder
```

## Building the .exe

```powershell
pwsh macro/build/build.ps1        # -> macro/build/dist/BiomeBeacon.exe
```

PyInstaller **onefile**, no UPX, windowed. Some antivirus engines distrust
self-extracting Python exes; since this project is open source, anyone can build
from source and compare. Switching to onedir (or Nuitka) is isolated to
`build/biomebeacon.spec` if false positives become a problem.
