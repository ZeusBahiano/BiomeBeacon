from __future__ import annotations

import queue
import time

import customtkinter as ctk

from ..config import MacroConfig
from ..version import APP_NAME, __version__
from .theme import BUTTON, COLORS, ENTRY, biome_hex, fmt_since

MAX_FEED_LINES = 400


class MainWindow(ctk.CTk):
    def __init__(self, config: MacroConfig, watcher, net, ui_queue: queue.Queue):
        super().__init__(fg_color=COLORS["bg"])
        self.config_data = config
        self.watcher = watcher
        self.net = net
        self.ui_queue = ui_queue
        self._accounts: dict[int, str] = {}
        self._biome_meta: dict[str, dict] = {}
        self._instances: list[dict] = []
        self._instance_rows: list[ctk.CTkFrame] = []
        self._paused = False

        self.title(f"{APP_NAME} v{__version__}")
        self.geometry("880x580")
        self.minsize(780, 500)

        self._build_header()
        self._build_tabs()
        self.after(150, self._poll_ui_queue)

    # ------------------------------------------------------------------ layout

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=COLORS["bg2"], corner_radius=0, height=56)
        header.pack(fill="x")
        title = ctk.CTkLabel(
            header,
            text="Biome",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text"],
        )
        title.pack(side="left", padx=(18, 0), pady=10)
        ctk.CTkLabel(
            header,
            text="Beacon",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["gold"],
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(
            header, text="Starting…", text_color=COLORS["muted"]
        )
        self.status_label.pack(side="right", padx=(0, 18))
        self.status_dot = ctk.CTkLabel(
            header, text="●", font=ctk.CTkFont(size=16), text_color=COLORS["muted"]
        )
        self.status_dot.pack(side="right", padx=(0, 6))

    def _build_tabs(self) -> None:
        self.tabs = ctk.CTkTabview(
            self,
            fg_color=COLORS["bg2"],
            segmented_button_fg_color=COLORS["card"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_hover"],
            segmented_button_unselected_color=COLORS["card"],
        )
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self._build_status_tab(self.tabs.add("Status"))
        self._build_settings_tab(self.tabs.add("Settings"))
        self._build_about_tab(self.tabs.add("About"))

    def _build_status_tab(self, tab) -> None:
        ctk.CTkLabel(
            tab, text="Roblox instances", text_color=COLORS["gold"],
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=8, pady=(6, 2))
        self.instances_frame = ctk.CTkFrame(tab, fg_color=COLORS["card"])
        self.instances_frame.pack(fill="x", padx=8)
        self._render_instances()

        ctk.CTkLabel(
            tab, text="Activity", text_color=COLORS["gold"],
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=8, pady=(12, 2))
        self.feed = ctk.CTkTextbox(
            tab, fg_color=COLORS["card"], text_color=COLORS["text"],
            font=ctk.CTkFont(family="Consolas", size=12), state="disabled", wrap="none",
        )
        self.feed.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.pause_btn = ctk.CTkButton(
            tab, text="Pause detection", command=self._toggle_pause, **BUTTON
        )
        self.pause_btn.pack(anchor="e", padx=8, pady=(0, 8))

    def _build_settings_tab(self, tab) -> None:
        body = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)

        def section(text):
            ctk.CTkLabel(
                body, text=text, text_color=COLORS["gold"],
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(anchor="w", padx=8, pady=(14, 4))

        section("Connection")
        self.server_entry = ctk.CTkEntry(
            body, placeholder_text="Server URL (e.g. https://biomes.mycommunity.com)",
            width=520, **ENTRY,
        )
        self.server_entry.pack(anchor="w", padx=8, pady=3)
        if self.config_data.server_url:
            self.server_entry.insert(0, self.config_data.server_url)

        self.key_entry = ctk.CTkEntry(
            body, placeholder_text="API key (from your community's /key create)",
            width=520, show="•", **ENTRY,
        )
        self.key_entry.pack(anchor="w", padx=8, pady=3)
        if self.config_data.api_key:
            self.key_entry.insert(0, self.config_data.api_key)

        ctk.CTkButton(
            body, text="Save & test connection", command=self._save_connection, **BUTTON
        ).pack(anchor="w", padx=8, pady=(6, 0))

        section("Private server")
        self.link_entry = ctk.CTkEntry(
            body, placeholder_text="https://www.roblox.com/share?code=…&type=Server",
            width=520, **ENTRY,
        )
        self.link_entry.pack(anchor="w", padx=8, pady=3)
        ctk.CTkButton(
            body, text="Update link", command=self._update_link, **BUTTON
        ).pack(anchor="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(
            body, text="This is the link hunters receive when a biome starts on your server.",
            text_color=COLORS["muted"],
        ).pack(anchor="w", padx=8)

        section("Advanced")
        self.logdir_entry = ctk.CTkEntry(
            body, placeholder_text="Log directory override (empty = default Roblox logs)",
            width=520, **ENTRY,
        )
        self.logdir_entry.pack(anchor="w", padx=8, pady=3)
        if self.config_data.log_dir:
            self.logdir_entry.insert(0, self.config_data.log_dir)
        ctk.CTkButton(body, text="Apply", command=self._apply_logdir, **BUTTON).pack(
            anchor="w", padx=8, pady=(6, 0)
        )

        self.minimized_var = ctk.BooleanVar(value=self.config_data.start_minimized)
        ctk.CTkCheckBox(
            body, text="Start minimized", variable=self.minimized_var,
            command=self._save_minimized, fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        ).pack(anchor="w", padx=8, pady=(10, 14))

    def _build_about_tab(self, tab) -> None:
        ctk.CTkLabel(
            tab, text=f"{APP_NAME} v{__version__}",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=COLORS["gold"],
        ).pack(pady=(30, 6))
        ctk.CTkLabel(
            tab,
            text=(
                "Open-source biome detector for Sol's RNG.\n"
                "Reads your Roblox client logs locally and alerts your community's\n"
                "Discord when a rare biome starts on your private server.\n\n"
                "It never touches the game process — log files only."
            ),
            text_color=COLORS["text"],
            justify="center",
        ).pack()
        ctk.CTkLabel(
            tab, text="github.com/<your-community>/biomebeacon",
            text_color=COLORS["muted"],
        ).pack(pady=(16, 0))

    # ----------------------------------------------------------------- actions

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.watcher.set_paused(self._paused)
        self.pause_btn.configure(
            text="Resume detection" if self._paused else "Pause detection"
        )
        self._feed_line("detection paused" if self._paused else "detection resumed")

    def _save_connection(self) -> None:
        self.config_data.server_url = self.server_entry.get().strip()
        self.config_data.api_key = self.key_entry.get().strip()
        self.config_data.save()
        self._feed_line("testing connection…")
        self.net.request_refresh()

    def _update_link(self) -> None:
        link = self.link_entry.get().strip()
        if link:
            self.net.submit_private_server(link)

    def _apply_logdir(self) -> None:
        self.config_data.log_dir = self.logdir_entry.get().strip()
        self.config_data.save()
        self.watcher.set_log_dir(self.config_data.effective_log_dir)
        self._feed_line(f"watching: {self.config_data.effective_log_dir}")

    def _save_minimized(self) -> None:
        self.config_data.start_minimized = bool(self.minimized_var.get())
        self.config_data.save()

    # ----------------------------------------------------------------- updates

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                kind, data = self.ui_queue.get_nowait()
                handler = getattr(self, f"_on_{kind}", None)
                if handler:
                    handler(data)
        except queue.Empty:
            pass
        self.after(150, self._poll_ui_queue)

    def _on_status(self, data: dict) -> None:
        color = COLORS["ok"] if data["connected"] else COLORS["err"]
        self.status_dot.configure(text_color=color)
        self.status_label.configure(text=data["text"], text_color=COLORS["text"])

    def _on_instances(self, snapshot: list[dict]) -> None:
        if snapshot != self._instances:
            self._instances = snapshot
            self._render_instances()

    def _on_account(self, data: dict) -> None:
        self._accounts[data["id"]] = data["name"]
        self._render_instances()

    def _on_event(self, data: dict) -> None:
        account = data.get("account") or self._accounts.get(data.get("roblox_user_id"))
        who = account or (str(data["roblox_user_id"]) if data.get("roblox_user_id") else "?")
        marker = "▶" if data["type"] == "started" else "■"
        self._feed_line(f"{marker} {data['biome']} {data['type']}  [{who}]")

    def _on_log(self, text: str) -> None:
        self._feed_line(text)

    def _on_config(self, remote: dict) -> None:
        self._biome_meta = {b["name"]: b for b in remote.get("biomes", [])}
        link = (remote.get("user") or {}).get("private_server_link")
        if link and not self.link_entry.get().strip():
            self.link_entry.insert(0, link)

    def _render_instances(self) -> None:
        for row in self._instance_rows:
            row.destroy()
        self._instance_rows = []
        if not self._instances:
            row = ctk.CTkFrame(self.instances_frame, fg_color="transparent")
            ctk.CTkLabel(
                row, text="No active Roblox instance detected.",
                text_color=COLORS["muted"],
            ).pack(side="left", padx=10, pady=8)
            row.pack(fill="x")
            self._instance_rows.append(row)
            return
        for inst in self._instances:
            row = ctk.CTkFrame(self.instances_frame, fg_color="transparent")
            uid = inst.get("roblox_user_id")
            account = self._accounts.get(uid) or (str(uid) if uid else "unknown account")
            ctk.CTkLabel(
                row, text=account, width=220, anchor="w", text_color=COLORS["text"],
            ).pack(side="left", padx=(10, 4), pady=4)
            biome = inst.get("biome") or "—"
            meta = self._biome_meta.get(biome, {})
            ctk.CTkLabel(
                row, text=biome,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=biome_hex(meta.get("color")),
            ).pack(side="left", padx=4)
            since = fmt_since(inst.get("biome_since"))
            if since:
                ctk.CTkLabel(
                    row, text=f"for {since}", text_color=COLORS["muted"],
                ).pack(side="left", padx=8)
            row.pack(fill="x")
            self._instance_rows.append(row)

    def _feed_line(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.feed.configure(state="normal")
        self.feed.insert("end", f"[{stamp}] {text}\n")
        lines = int(self.feed.index("end-1c").split(".")[0])
        if lines > MAX_FEED_LINES:
            self.feed.delete("1.0", f"{lines - MAX_FEED_LINES}.0")
        self.feed.see("end")
        self.feed.configure(state="disabled")
