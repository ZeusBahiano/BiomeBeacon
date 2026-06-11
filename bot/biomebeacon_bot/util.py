from __future__ import annotations

from datetime import datetime

from .db import as_utc


def discord_ts(dt: datetime | None, style: str = "R") -> str:
    """Discord timestamp markup (<t:unix:R> renders as 'x hours ago')."""
    if dt is None:
        return "never"
    return f"<t:{int(as_utc(dt).timestamp())}:{style}>"
