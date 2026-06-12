# PyInstaller spec — onefile, no UPX, no console window.
# Build with:  pwsh macro/build/build.ps1   (or: pyinstaller macro/build/biomebeacon.spec)
#
# Anti-virus notes (docs/SELF_HOSTING.md): onefile self-extracts, which some AVs
# dislike. If false positives become a problem, switching to onedir is a
# one-line change here (move a.binaries/a.datas out of EXE into a COLLECT).

import os

MACRO_DIR = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH is injected)

a = Analysis(  # noqa: F821
    [os.path.join(MACRO_DIR, "run_biomebeacon.py")],
    pathex=[MACRO_DIR],
    binaries=[],
    # HTML/CSS/JS interface, served to the WebView2 window from the bundle
    datas=[(os.path.join(MACRO_DIR, "biomebeacon", "webui"), "biomebeacon/webui")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "mongomock", "motor", "pymongo", "nextcord"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="BiomeBeacon",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
