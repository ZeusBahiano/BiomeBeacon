"""Sol's RNG-inspired dark theme (deep purple night sky + gold accents)."""

from __future__ import annotations

import time

import customtkinter as ctk

COLORS = {
    "bg": "#0d0716",
    "bg2": "#160b26",
    "card": "#1e1233",
    "card2": "#271a40",
    "border": "#32235a",
    "accent": "#7c3aed",
    "accent_hover": "#8f5bf0",
    "gold": "#ffd76a",
    "text": "#e8e3f5",
    "muted": "#9a8fc0",
    "ok": "#46c97a",
    "err": "#e5484d",
}

BUTTON = {"fg_color": COLORS["accent"], "hover_color": COLORS["accent_hover"]}
ENTRY = {
    "fg_color": COLORS["card2"],
    "border_color": COLORS["border"],
    "text_color": COLORS["text"],
}


def setup_appearance() -> None:
    ctk.set_appearance_mode("dark")


def biome_hex(color: int | None) -> str:
    return f"#{(color if color is not None else 0x9B9B9B):06x}"


def fmt_since(epoch: float | None) -> str:
    if not epoch:
        return ""
    minutes = int((time.time() - epoch) // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h {minutes % 60:02d}m"
