"""Log directory watcher thread.

Every poll it looks at *.log files modified recently (each Roblox instance owns
one), reads only the new bytes since the previous poll, and feeds complete lines
to the engine. A file seen for the first time is *seeded*: its existing content
is replayed silently so the engine learns the current biome without re-emitting
historical transitions (prevents alert spam on macro restart).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

from .engine import BiomeEvent, DetectionEngine

log = logging.getLogger(__name__)

ACTIVE_WINDOW = 120.0  # seconds without writes before an instance is considered gone


class LogWatcher(threading.Thread):
    def __init__(
        self,
        log_dir: Path,
        engine: DetectionEngine,
        events_queue: queue.Queue,
        ui_queue: queue.Queue,
        poll_interval: float = 2.0,
    ):
        super().__init__(name="bb-logwatcher", daemon=True)
        self.log_dir = Path(log_dir)
        self.engine = engine
        self.events_queue = events_queue
        self.ui_queue = ui_queue
        self.poll_interval = poll_interval
        self._offsets: dict[str, int] = {}
        self._buffers: dict[str, bytes] = {}
        self._stop = threading.Event()
        self._paused = threading.Event()

    # -- control (called from the UI thread) --------------------------------

    def stop(self) -> None:
        self._stop.set()

    def set_paused(self, paused: bool) -> None:
        if paused:
            self._paused.set()
        else:
            self._paused.clear()

    def set_log_dir(self, log_dir: Path) -> None:
        self.log_dir = Path(log_dir)
        self._offsets.clear()
        self._buffers.clear()
        self.engine.instances.clear()

    # -- loop ----------------------------------------------------------------

    def run(self) -> None:
        while not self._stop.is_set():
            if not self._paused.is_set():
                try:
                    self.scan_once()
                except Exception:
                    log.exception("log scan failed")
            self._stop.wait(self.poll_interval)

    def scan_once(self) -> None:
        now = time.time()
        active: dict[str, Path] = {}
        if self.log_dir.is_dir():
            for path in self.log_dir.glob("*.log"):
                try:
                    if now - path.stat().st_mtime <= ACTIVE_WINDOW:
                        active[path.name] = path
                except OSError:
                    continue

        # Instances whose logs went quiet: forget them (no synthetic events).
        for known in list(self.engine.instances):
            if known not in active:
                self.engine.drop_instance(known)
                self._offsets.pop(known, None)
                self._buffers.pop(known, None)

        for name, path in active.items():
            seeding = name not in self._offsets
            for event in self._read_new_lines(name, path):
                if not seeding:
                    self.events_queue.put(event)

        self._push_snapshot()

    def _read_new_lines(self, name: str, path: Path) -> list[BiomeEvent]:
        offset = self._offsets.get(name, 0)
        try:
            size = path.stat().st_size
            if size < offset:  # truncated/replaced: re-read silently
                offset = 0
                self._buffers.pop(name, None)
            with path.open("rb") as fh:
                fh.seek(offset)
                chunk = fh.read()
                self._offsets[name] = fh.tell()
        except OSError as exc:
            log.warning("could not read %s: %s", name, exc)
            return []

        data = self._buffers.pop(name, b"") + chunk
        if not data:
            return []
        lines, _, remainder = data.rpartition(b"\n")
        if remainder:
            self._buffers[name] = remainder  # keep the partial last line for next poll
        events: list[BiomeEvent] = []
        if lines:
            for raw in lines.split(b"\n"):
                line = raw.decode("utf-8", errors="ignore")
                events.extend(self.engine.process_line(name, line))
        return events

    def _push_snapshot(self) -> None:
        snapshot = [
            {
                "instance": st.instance,
                "biome": st.biome,
                "biome_since": st.biome_since,
                "roblox_user_id": st.roblox_user_id,
            }
            for st in self.engine.snapshot()
        ]
        self.ui_queue.put(("instances", snapshot))
