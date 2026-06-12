"""pywebview shell: a frameless native window (WebView2) hosting the HTML UI.

The JS side calls the `Api` methods through `pywebview.api.*`; updates flow the
other way by polling `Api.poll()`, which drains the same thread-safe `ui_queue`
the watcher and net worker already write to.
"""

from __future__ import annotations

import queue
import sys
import webbrowser
from pathlib import Path

import webview

from ..config import MacroConfig
from ..version import APP_NAME, __version__


def asset_dir() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)  # PyInstaller onefile extraction dir
    if bundle:
        return Path(bundle) / "biomebeacon" / "webui"
    return Path(__file__).resolve().parent.parent / "webui"


class Api:
    """Methods exposed to JavaScript. Return values must be JSON-serializable."""

    def __init__(self, config: MacroConfig, watcher, net, ui_queue: queue.Queue):
        self.config = config
        self.watcher = watcher
        self.net = net
        self.ui_queue = ui_queue
        self.window: webview.Window | None = None
        self._paused = False

    def get_initial(self) -> dict:
        return {
            "app": APP_NAME,
            "version": __version__,
            "server_url": self.config.server_url,
            "api_key": self.config.api_key,
            "log_dir": self.config.log_dir,
            "theme": self.config.theme,
            "start_minimized": self.config.start_minimized,
        }

    def poll(self) -> list:
        messages = []
        try:
            while len(messages) < 50:
                messages.append(self.ui_queue.get_nowait())
        except queue.Empty:
            pass
        return messages

    def save_connection(self, server_url: str, api_key: str) -> bool:
        self.config.server_url = server_url.strip()
        self.config.api_key = api_key.strip()
        self.config.save()
        self.net.request_refresh()
        return True

    def request_refresh(self) -> bool:
        self.net.request_refresh()
        return True

    def update_link(self, link: str) -> bool:
        self.net.submit_private_server(link.strip())
        return True

    def apply_logdir(self, log_dir: str) -> str:
        self.config.log_dir = log_dir.strip()
        self.config.save()
        self.watcher.set_log_dir(self.config.effective_log_dir)
        return str(self.config.effective_log_dir)

    def set_paused(self, paused: bool) -> bool:
        self._paused = bool(paused)
        self.watcher.set_paused(self._paused)
        return self._paused

    def set_theme(self, theme: str) -> bool:
        self.config.theme = str(theme)
        self.config.save()
        return True

    def set_start_minimized(self, enabled: bool) -> bool:
        self.config.start_minimized = bool(enabled)
        self.config.save()
        return True

    def open_url(self, url: str) -> bool:
        # only credit/help links from our own HTML reach this; still, be strict
        if not url.startswith("https://"):
            return False
        webbrowser.open(url)
        return True

    def minimize(self) -> None:
        if self.window:
            self.window.minimize()

    def close_window(self) -> None:
        if self.window:
            self.window.destroy()


def run_ui(config: MacroConfig, watcher, net, ui_queue: queue.Queue) -> None:
    """Blocks until the window is closed (the GUI 'mainloop')."""
    api = Api(config, watcher, net, ui_queue)
    window = webview.create_window(
        APP_NAME,
        url=str(asset_dir() / "index.html"),
        js_api=api,
        width=1000,
        height=640,
        min_size=(860, 560),
        frameless=True,
        background_color="#0a1a14",
    )
    api.window = window

    def on_start(win: webview.Window) -> None:
        if config.start_minimized:
            win.minimize()

    webview.start(on_start, window)
