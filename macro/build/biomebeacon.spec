# PyInstaller spec — onefile, no UPX, no console window.
# Build with:  pwsh macro/build/build.ps1   (or: pyinstaller macro/build/biomebeacon.spec)
#
# Anti-virus notes (docs/SELF_HOSTING.md): onefile self-extracts, which some AVs
# dislike. If false positives become a problem, switching to onedir is a
# one-line change here (move a.binaries/a.datas out of EXE into a COLLECT).

import os

from PyInstaller.utils.hooks import collect_data_files

MACRO_DIR = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH is injected)

a = Analysis(  # noqa: F821
    [os.path.join(MACRO_DIR, "run_biomebeacon.py")],
    pathex=[MACRO_DIR],
    binaries=[],
    datas=collect_data_files("customtkinter"),
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
