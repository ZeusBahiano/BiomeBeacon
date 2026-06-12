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
    """Methods exposed to JavaScript. Return values must be JSON-serializable.

    Every attribute MUST be underscore-prefixed: pywebview walks public
    attributes recursively to build the JS bridge, and following watcher/net/
    window object graphs deadlocks window creation (Window waits for the
    bridge, the bridge's getattr on Window waits for the window).
    """

    def __init__(self, config: MacroConfig, watcher, net, ui_queue: queue.Queue):
        self._config = config
        self._watcher = watcher
        self._net = net
        self._ui_queue = ui_queue
        self._window: webview.Window | None = None
        self._paused = False

    def get_initial(self) -> dict:
        return {
            "app": APP_NAME,
            "version": __version__,
            "server_url": self._config.server_url,
            "api_key": self._config.api_key,
            "log_dir": self._config.log_dir,
            "theme": self._config.theme,
            "start_minimized": self._config.start_minimized,
        }

    def poll(self) -> list:
        messages = []
        try:
            while len(messages) < 50:
                messages.append(self._ui_queue.get_nowait())
        except queue.Empty:
            pass
        return messages

    def save_connection(self, server_url: str, api_key: str) -> bool:
        self._config.server_url = server_url.strip()
        self._config.api_key = api_key.strip()
        self._config.save()
        self._net.request_refresh()
        return True

    def request_refresh(self) -> bool:
        self._net.request_refresh()
        return True

    def update_link(self, link: str) -> bool:
        self._net.submit_private_server(link.strip())
        return True

    def apply_logdir(self, log_dir: str) -> str:
        self._config.log_dir = log_dir.strip()
        self._config.save()
        self._watcher.set_log_dir(self._config.effective_log_dir)
        return str(self._config.effective_log_dir)

    def set_paused(self, paused: bool) -> bool:
        self._paused = bool(paused)
        self._watcher.set_paused(self._paused)
        return self._paused

    def set_theme(self, theme: str) -> bool:
        self._config.theme = str(theme)
        self._config.save()
        return True

    def set_start_minimized(self, enabled: bool) -> bool:
        self._config.start_minimized = bool(enabled)
        self._config.save()
        return True

    def open_url(self, url: str) -> bool:
        # only credit/help links from our own HTML reach this; still, be strict
        if not url.startswith("https://"):
            return False
        webbrowser.open(url)
        return True

    def minimize(self) -> None:
        if self._window:
            self._window.minimize()

    def close_window(self) -> None:
        if self._window:
            self._window.destroy()


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
    api._window = window

    def on_start(win: webview.Window) -> None:
        if config.start_minimized:
            win.minimize()

    webview.start(on_start, window)
