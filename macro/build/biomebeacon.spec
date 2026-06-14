# PyInstaller spec — onefile, no UPX, no console window.
# Build with:  pwsh macro/build/build.ps1   (or: pyinstaller macro/build/biomebeacon.spec)
#
# Anti-virus notes (docs/SELF_HOSTING.md): onefile self-extracts, which some AVs
# dislike. If false positives become a problem, switching to onedir is a
# one-line change here (move a.binaries/a.datas out of EXE into a COLLECT).

import os

MACRO_DIR = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH is injected)
REPO_ROOT = os.path.abspath(os.path.join(MACRO_DIR, ".."))

a = Analysis(  # noqa: F821
    [os.path.join(MACRO_DIR, "run_biomebeacon.py")],
    pathex=[MACRO_DIR],
    binaries=[],
    datas=[
        # HTML/CSS/JS interface, served to the WebView2 window from the bundle
        (os.path.join(MACRO_DIR, "biomebeacon", "webui"), "biomebeacon/webui"),
        # License compliance (Apache-2.0 §4 — Noteab-Macro material): the same
        # files are also staged next to the .exe by build.ps1 for distribution.
        (os.path.join(REPO_ROOT, "LICENSE"), "."),
        (os.path.join(REPO_ROOT, "THIRD_PARTY_NOTICES.md"), "."),
        (os.path.join(REPO_ROOT, "LICENSES"), "LICENSES"),
    ],
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
