"use strict";

const API = "/api/v1/admin";
const $ = (sel) => document.querySelector(sel);

let token = localStorage.getItem("bb_admin_token") || "";

async function api(path, opts = {}) {
  const resp = await fetch(API + path, {
    ...opts,
    headers: {
      "Authorization": "Bearer " + token,
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  });
  if (resp.status === 401) {
    showLogin("Token rejected — sign in again.");
    throw new Error("unauthorized");
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || ("HTTP " + resp.status));
  return data;
}

function esc(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

// ---------- login ----------

function showLogin(message) {
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  $("#login-error").textContent = message || "";
}

async function tryLogin() {
  try {
    await api("/stats");
    $("#login").classList.add("hidden");
    $("#app").classList.remove("hidden");
    loadTab("overview");
  } catch (err) {
    if (err.message !== "unauthorized") showLogin(err.message);
  }
}

$("#login-btn").addEventListener("click", () => {
  token = $("#login-token").value.trim();
  localStorage.setItem("bb_admin_token", token);
  tryLogin();
});
$("#login-token").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#login-btn").click();
});
$("#logout").addEventListener("click", () => {
  localStorage.removeItem("bb_admin_token");
  token = "";
  showLogin("");
});

// ---------- tabs ----------

document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".panel").forEach((p) => p.classList.add("hidden"));
    $("#tab-" + btn.dataset.tab).classList.remove("hidden");
    loadTab(btn.dataset.tab);
  })
);

function loadTab(name) {
  ({ overview: loadOverview, users: loadUsers, biomes: loadBiomes,
     settings: loadSettings, events: loadEvents })[name]();
}

// ---------- overview ----------

async function loadOverview() {
  const s = await api("/stats");
  const cards = [
    [s.users_total, "users"], [s.users_active, "active"],
    [s.events_24h, "events / 24h"], [s.dispatch_mode, "mode"],
    [s.relay ? "relay" : "direct", "webhook flow"],
  ];
  $("#stats").innerHTML = cards
    .map(([num, label]) => `<div class="card"><div class="num">${esc(num)}</div><div class="label">${esc(label)}</div></div>`)
    .join("");
  $("#broken").innerHTML = s.broken_webhooks.length
    ? s.broken_webhooks.map((b) => `<li>⚠️ ${esc(b)}</li>`).join("")
    : "<li>none 🎉</li>";
}

// ---------- users ----------

async function loadUsers() {
  const { users } = await api("/users");
  const rows = users.map((u) => `
    <tr data-id="${esc(u.discord_id)}">
      <td>${esc(u.discord_name)}<br><span class="hint">${esc(u.discord_id)}</span></td>
      <td><code>${esc(u.key_prefix)}…</code></td>
      <td><span class="badge ${u.active ? "on" : "off"}">${u.active ? "active" : "inactive"}</span></td>
      <td>${fmtDate(u.last_seen)}</td>
      <td>${esc(u.macro_version || "—")} ${u.instances ? "(" + esc(u.instances) + "x)" : ""}</td>
      <td>
        <button class="small" data-act="toggle">${u.active ? "Deactivate" : "Activate"}</button>
        <button class="small" data-act="regen">New key</button>
        <button class="small danger" data-act="del">Delete</button>
      </td>
    </tr>`).join("");
  $("#users-table").innerHTML =
    "<tr><th>User</th><th>Key</th><th>Status</th><th>Last seen</th><th>Macro</th><th></th></tr>" + rows;

  $("#users-table").querySelectorAll("button").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const id = btn.closest("tr").dataset.id;
      const act = btn.dataset.act;
      try {
        if (act === "toggle") {
          const isActive = btn.textContent === "Deactivate";
          await api(`/users/${id}`, { method: "PATCH", body: JSON.stringify({ active: !isActive }) });
        } else if (act === "regen") {
          const { key } = await api(`/users/${id}/regenerate-key`, { method: "POST" });
          prompt("New key (shown ONCE — send it to the user):", key);
        } else if (act === "del") {
          if (!confirm(`Delete user ${id}? The bot won't clean their Discord channel.`)) return;
          await api(`/users/${id}`, { method: "DELETE" });
        }
        loadUsers();
      } catch (err) { alert(err.message); }
    })
  );
}

// ---------- biomes ----------

async function loadBiomes() {
  const { biomes } = await api("/biomes");
  const rarities = ["common", "rare", "legendary"];
  const rows = biomes.map((b) => `
    <tr data-name="${esc(b.name)}">
      <td><strong>${esc(b.name)}</strong></td>
      <td><input class="f-display" value="${esc(b.display)}"></td>
      <td><input class="f-color" type="color" value="#${Number(b.color).toString(16).padStart(6, "0")}"></td>
      <td><input class="f-image" value="${esc(b.image_url || "")}" placeholder="thumbnail url"></td>
      <td><input class="f-notify" type="checkbox" ${b.notify ? "checked" : ""}></td>
      <td><input class="f-ping" value="${esc(b.ping_role_id || "")}" placeholder="role id"></td>
      <td><input class="f-webhook" value="${esc(b.webhook_url || "")}" placeholder="webhook (per-biome mode)">
          ${b.webhook_broken ? '<span class="badge off">broken</span>' : ""}</td>
      <td><select class="f-rarity">${rarities.map((r) =>
        `<option ${r === b.rarity ? "selected" : ""}>${r}</option>`).join("")}</select></td>
      <td><button class="small" data-act="save">Save</button>
          <button class="small danger" data-act="del">✕</button></td>
    </tr>`).join("");
  $("#biomes-table").innerHTML =
    "<tr><th>Name</th><th>Display</th><th>Color</th><th>Image</th><th>Notify</th><th>Ping role</th><th>Webhook</th><th>Rarity</th><th></th></tr>" + rows;

  $("#biomes-table").querySelectorAll("button").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const tr = btn.closest("tr");
      const name = tr.dataset.name;
      try {
        if (btn.dataset.act === "del") {
          if (!confirm(`Delete biome ${name}?`)) return;
          await api(`/biomes/${encodeURIComponent(name)}`, { method: "DELETE" });
        } else {
          const body = {
            display: tr.querySelector(".f-display").value,
            color: parseInt(tr.querySelector(".f-color").value.slice(1), 16),
            image_url: tr.querySelector(".f-image").value || null,
            notify: tr.querySelector(".f-notify").checked,
            ping_role_id: parseInt(tr.querySelector(".f-ping").value) || null,
            webhook_url: tr.querySelector(".f-webhook").value || null,
            rarity: tr.querySelector(".f-rarity").value,
          };
          await api(`/biomes/${encodeURIComponent(name)}`, { method: "PUT", body: JSON.stringify(body) });
        }
        loadBiomes();
      } catch (err) { alert(err.message); }
    })
  );
}

$("#add-biome").addEventListener("click", async () => {
  const name = $("#new-biome-name").value.trim().toUpperCase();
  if (!name) return;
  try {
    await api(`/biomes/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify({ display: name[0] + name.slice(1).toLowerCase() }),
    });
    $("#new-biome-name").value = "";
    loadBiomes();
  } catch (err) { alert(err.message); }
});

// ---------- settings ----------

const SETTING_FIELDS = [
  ["dispatch_mode", "select", ["single_channel", "per_biome_channels", "per_user_channels"]],
  ["relay", "checkbox"],
  ["single_channel_webhook", "text"],
  ["inactivity_enabled", "checkbox"],
  ["inactivity_days", "number"],
  ["min_macro_version", "text"],
  ["heartbeat_interval", "number"],
];

async function loadSettings() {
  const s = await api("/settings");
  $("#settings-form").innerHTML = SETTING_FIELDS.map(([key, kind, options]) => {
    let input;
    if (kind === "select") {
      input = `<select name="${key}">${options.map((o) =>
        `<option ${o === s[key] ? "selected" : ""}>${o}</option>`).join("")}</select>`;
    } else if (kind === "checkbox") {
      input = `<input name="${key}" type="checkbox" ${s[key] ? "checked" : ""}>`;
    } else {
      input = `<input name="${key}" type="${kind}" value="${esc(s[key] ?? "")}">`;
    }
    return `<label>${key.replaceAll("_", " ")}</label>${input}`;
  }).join("") + `<span></span><button type="submit">Save settings</button>`;
}

$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const body = {};
  for (const [key, kind] of SETTING_FIELDS) {
    const el = form.elements[key];
    if (kind === "checkbox") body[key] = el.checked;
    else if (kind === "number") body[key] = parseInt(el.value) || undefined;
    else if (el.value !== "") body[key] = el.value;
  }
  try {
    await api("/settings", { method: "PATCH", body: JSON.stringify(body) });
    $("#settings-msg").textContent = "Saved ✔ (macros pick it up on their next heartbeat)";
  } catch (err) {
    $("#settings-msg").textContent = "Error: " + err.message;
  }
});

$("#test-webhook").addEventListener("click", async () => {
  const target = $("#test-target").value.trim() || "single";
  try {
    await api("/test-webhook", { method: "POST", body: JSON.stringify({ target }) });
    $("#settings-msg").textContent = `Test sent to '${target}' ✔`;
  } catch (err) {
    $("#settings-msg").textContent = "Error: " + err.message;
  }
});

// ---------- events ----------

async function loadEvents() {
  const params = new URLSearchParams({ limit: "100" });
  if ($("#ev-user").value.trim()) params.set("user", $("#ev-user").value.trim());
  if ($("#ev-biome").value.trim()) params.set("biome", $("#ev-biome").value.trim());
  const { events } = await api("/events?" + params);
  const rows = events.map((ev) => `
    <tr>
      <td>${fmtDate(ev.server_ts)}</td>
      <td><strong>${esc(ev.biome)}</strong></td>
      <td>${ev.type === "started" ? "▶" : "■"} ${esc(ev.type)}</td>
      <td>${esc(ev.user_id)}</td>
      <td>${esc(ev.roblox_user_id || "—")}</td>
      <td>${ev.dispatched ? "✔" : "—"}</td>
    </tr>`).join("");
  $("#events-table").innerHTML =
    "<tr><th>When</th><th>Biome</th><th>Type</th><th>User</th><th>Roblox acc</th><th>Sent</th></tr>" + rows;
}

$("#ev-refresh").addEventListener("click", loadEvents);

// ---------- boot ----------

if (token) tryLogin(); else showLogin("");
