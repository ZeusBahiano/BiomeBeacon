"use strict";

const $ = (sel) => document.querySelector(sel);

let biomeMeta = {};   // BIOME -> {display, color, ...} from server config
let accounts = {};    // roblox uid -> username
let instances = [];
let paused = false;

const hex = (c) => "#" + ((c ?? 0x9aa3ad) >>> 0).toString(16).padStart(6, "0");

function fmtSince(epoch) {
  if (!epoch) return "";
  const m = Math.floor((Date.now() / 1000 - epoch) / 60);
  if (m < 1) return "just now";
  if (m < 60) return `for ${m}m`;
  return `for ${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}

function esc(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

// ------------------------------------------------------------------ feed

function feedLine(text, cls = "line") {
  const feed = $("#feed");
  const stamp = new Date().toLocaleTimeString();
  const div = document.createElement("div");
  div.innerHTML = `<span class="t">[${stamp}]</span><span class="${cls}">${esc(text)}</span>`;
  feed.appendChild(div);
  while (feed.childElementCount > 400) feed.removeChild(feed.firstChild);
  feed.scrollTop = feed.scrollHeight;
}

// ----------------------------------------------------------------- tiles

function renderTiles() {
  const tiles = $("#tiles");
  $("#tab-count").textContent = instances.length;
  $("#info-instances").textContent = instances.length;
  if (!instances.length) {
    tiles.innerHTML =
      '<div class="tile empty"><div class="biome">NO ROBLOX</div>' +
      '<div class="acct">waiting for the game…</div></div>';
    updateShowcase();
    return;
  }
  tiles.innerHTML = instances
    .map((inst) => {
      const biome = inst.biome || "…";
      const meta = biomeMeta[biome] || {};
      const account =
        accounts[inst.roblox_user_id] ||
        (inst.roblox_user_id ? `#${inst.roblox_user_id}` : "unknown account");
      return `<div class="tile" style="--tile:${hex(meta.color)}">
        <div class="biome">${esc(biome)}</div>
        <div class="acct">${esc(account)}</div>
        <div class="since">${fmtSince(inst.biome_since)}</div>
      </div>`;
    })
    .join("");
  updateShowcase();
}

function updateShowcase() {
  const show = $("#show-biome");
  const sub = $("#show-sub");
  const active = instances.filter((i) => i.biome);
  if (!active.length) {
    show.style.setProperty("--show", "#9aa3ad");
    show.textContent = "—";
    sub.textContent = "no active instance";
    return;
  }
  // highlight the most interesting biome: anything that's not NORMAL wins
  const pick = active.find((i) => i.biome !== "NORMAL") || active[0];
  const meta = biomeMeta[pick.biome] || {};
  show.style.setProperty("--show", hex(meta.color));
  show.textContent = pick.biome;
  sub.textContent = `${fmtSince(pick.biome_since)} · ${active.length} instance(s)`;
}

// -------------------------------------------------------- message handlers

const handlers = {
  status(data) {
    $("#status-dot").style.color = data.connected ? "#46c97a" : "#e5484d";
    $("#status-text").textContent = data.text;
  },
  instances(data) {
    instances = data;
    renderTiles();
  },
  account(data) {
    accounts[data.id] = data.name;
    renderTiles();
  },
  event(data) {
    const who =
      data.account || accounts[data.roblox_user_id] ||
      (data.roblox_user_id ? `#${data.roblox_user_id}` : "?");
    const marker = data.type === "started" ? "▶" : "■";
    feedLine(`${marker} ${data.biome} ${data.type}  [${who}]`, "line event");
    $("#info-last").textContent = `${data.biome} ${data.type}`;
  },
  log(text) {
    feedLine(text);
  },
  config(remote) {
    biomeMeta = {};
    for (const b of remote.biomes || []) biomeMeta[b.name] = b;
    $("#info-server").textContent = remote.server_name || "—";
    $("#info-mode").textContent = remote.dispatch?.relay ? "relay (via server)" : "direct webhook";
    const link = remote.user?.private_server_link;
    if (link && !$("#set-link").value.trim()) $("#set-link").value = link;
    renderTiles();
  },
};

async function poll() {
  try {
    const messages = await pywebview.api.poll();
    for (const [kind, data] of messages) handlers[kind]?.(data);
  } catch (err) {
    /* bridge not ready yet */
  }
}

// ----------------------------------------------------------------- wiring

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === name)
  );
  document.querySelectorAll(".tab-page").forEach((p) =>
    p.classList.toggle("hidden", p.id !== "tab-" + name)
  );
}

function wire() {
  document.querySelectorAll(".tab-btn").forEach((b) =>
    b.addEventListener("click", () => switchTab(b.dataset.tab))
  );
  $("#btn-min").addEventListener("click", () => pywebview.api.minimize());
  $("#btn-close").addEventListener("click", () => pywebview.api.close_window());

  $("#btn-pause").addEventListener("click", async () => {
    paused = await pywebview.api.set_paused(!paused);
    const btn = $("#btn-pause");
    btn.textContent = paused ? "Resume Detection" : "Pause Detection";
    btn.classList.toggle("red", !paused);
    btn.classList.toggle("blue", paused);
    feedLine(paused ? "detection paused" : "detection resumed");
  });

  $("#btn-test").addEventListener("click", () => {
    feedLine("testing connection…");
    pywebview.api.request_refresh();
  });

  $("#btn-save").addEventListener("click", () => {
    pywebview.api.save_connection($("#set-url").value.trim(), $("#set-key").value.trim());
    feedLine("connection settings saved — testing…");
    switchTab("status");
  });

  $("#btn-link").addEventListener("click", () => {
    const link = $("#set-link").value.trim();
    if (link) pywebview.api.update_link(link);
  });

  $("#btn-logdir").addEventListener("click", async () => {
    const dir = await pywebview.api.apply_logdir($("#set-logdir").value.trim());
    feedLine(`watching: ${dir}`);
  });
}

async function init() {
  wire();
  const initial = await pywebview.api.get_initial();
  $("#version").textContent = "v" + initial.version;
  if (initial.server_url) $("#set-url").value = initial.server_url;
  if (initial.api_key) $("#set-key").value = initial.api_key;
  if (initial.log_dir) $("#set-logdir").value = initial.log_dir;
  renderTiles();
  feedLine("BiomeBeacon started");
  setInterval(poll, 400);
}

window.addEventListener("pywebviewready", init);
