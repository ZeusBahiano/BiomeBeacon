from __future__ import annotations

import logging
import queue

from .config import MacroConfig
from .detection.engine import DetectionEngine
from .detection.watcher import LogWatcher
from .net.client import NetWorker
from .ui.main_window import MainWindow
from .ui.theme import setup_appearance


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    config = MacroConfig.load()
    events_queue: queue.Queue = queue.Queue()
    ui_queue: queue.Queue = queue.Queue()

    engine = DetectionEngine()
    watcher = LogWatcher(
        config.effective_log_dir, engine, events_queue, ui_queue, config.poll_interval
    )

    def apply_place_ids(place_ids: list[int]) -> None:
        engine.place_ids = place_ids

    net = NetWorker(
        config,
        events_queue,
        ui_queue,
        instances_fn=lambda: len(engine.instances),
        on_place_ids=apply_place_ids,
    )

    watcher.start()
    net.start()

    setup_appearance()
    window = MainWindow(config, watcher, net, ui_queue)
    if config.start_minimized:
        window.iconify()
    try:
        window.mainloop()
    finally:
        watcher.stop()
        net.stop()
