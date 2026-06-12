"""PyInstaller entry point (a plain script avoids relative-import issues
that `python -m biomebeacon` would cause inside the bundle)."""

from biomebeacon.app import main

main()
