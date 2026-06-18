const dom = {
  authSection: document.getElementById("authSection"),
  appSection: document.getElementById("appSection"),
  loginForm: document.getElementById("loginForm"),
  logoutBtn: document.getElementById("logoutBtn"),
  userBox: document.getElementById("userBox"),
  channelsTable: document.querySelector("#channelsTable tbody"),
  recordingsTable: document.querySelector("#recordingsTable tbody"),
  playlistList: document.getElementById("playlistList"),
  addChannelForm: document.getElementById("addChannelForm"),
  createPlaylistForm: document.getElementById("createPlaylistForm"),
};

const state = {
  channels: [],
  recordings: [],
  playlists: [],
};

function api(path, options = {}) {
  return fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "include",
    ...options,
  }).then(async (res) => {
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || `${res.status}`);
    }
    return res.status === 204 ? null : res.json();
  });
}

function showAuthMode(connected) {
  dom.authSection.style.display = connected ? "none" : "block";
  dom.appSection.style.display = connected ? "block" : "none";
  dom.userBox.textContent = connected ? "Admin session active" : "";
}

async function checkSession() {
  try {
    await api("/api/auth/me");
    showAuthMode(true);
    await loadAll();
  } catch {
    showAuthMode(false);
  }
}

function playlistOptionsHTML(selectedId) {
  const list = state.playlists.map((p) => `<option value="${p.id}" ${p.id === selectedId ? "selected" : ""}>${p.name}</option>`);
  return `<option value="">None</option>${list.join("")}`;
}

function renderChannels() {
  const rows = state.channels.map((channel) => {
    const select = `<select data-action="updatePlaylist" data-id="${channel.id}">
      ${playlistOptionsHTML(channel.auto_playlist_id)}
    </select>`;
    const checked = channel.auto_add_to_playlist ? "checked" : "";
    return `<tr>
      <td>
        <div><strong>${channel.twitch_username}</strong></div>
        <div class="muted">${channel.display_name || ""}</div>
      </td>
      <td>${channel.status || "offline"} ${channel.is_live ? "• live" : ""}</td>
      <td>
        <label class="inline">
          <input type="checkbox" data-action="toggleAuto" data-id="${channel.id}" ${checked} />
          Auto-add
        </label>
        ${select}
      </td>
      <td>
        <button data-action="deleteChannel" data-id="${channel.id}">Delete</button>
      </td>
    </tr>`;
  }).join("");
  dom.channelsTable.innerHTML = rows || `<tr><td colspan="4" class="muted">No channel yet</td></tr>`;
}

function renderRecordings() {
  const rows = state.recordings.map((rec) => {
    const shareUrl = rec.share_key ? `<a href="/share/${rec.share_key}" target="_blank">/share/${rec.share_key}</a>` : "";
    const status = rec.status;
    const shareState = rec.share_enabled ? "Enabled" : "Disabled";
    return `<tr>
      <td>${rec.channel}</td>
      <td>${rec.started_at ? new Date(rec.started_at).toLocaleString() : ""}</td>
      <td>
        <input value="${escapeHtml(rec.title_display)}" data-title="${rec.id}" />
        <button data-action="rename" data-id="${rec.id}">Save</button>
      </td>
      <td>${status}</td>
      <td>
        <input placeholder="custom slug (3-80)" data-slug="${rec.id}" value="${rec.share_slug || ""}" />
        <button data-action="share" data-id="${rec.id}">Create / Update</button><br/>
        <span class="muted">${shareState}</span>
        ${shareUrl ? `<div class="muted">${shareUrl}</div>` : ""}
      </td>
      <td>
        ${rec.id ? `<a href="/api/media/${rec.id}" target="_blank">Admin media</a> | ` : ""}
        <button data-action="revoke" data-id="${rec.id}">Revoke</button>
      </td>
    </tr>`;
  }).join("");
  dom.recordingsTable.innerHTML = rows || `<tr><td colspan="6" class="muted">No recording yet</td></tr>`;
}

function recordingOptions() {
  return state.recordings
    .filter((r) => r.status === "completed")
    .map((r) => `<option value="${r.id}">${r.channel} - ${escapeHtml(r.title_display || "")}</option>`)
    .join("");
}

function renderPlaylists() {
  dom.playlistList.innerHTML = state.playlists
    .map((p) => {
      const items = p.items
        .map(
          (item) => `<li>${item.recording_title || item.recording_id} <button data-action="removePlaylistItem" data-playlist="${p.id}" data-recording="${item.recording_id}">Remove</button></li>`
        )
        .join("");
      return `<div class="playlist-block">
        <h3>${escapeHtml(p.name)}</h3>
        <ul>${items || "<li class='muted'>empty playlist</li>"}</ul>
        <div class="inline-row">
          <select data-playlist-recording="${p.id}">
            ${recordingOptions()}
          </select>
          <button data-action="addPlaylistItem" data-playlist="${p.id}">Add to top</button>
        </div>
      </div>`;
    })
    .join("");
}

function render() {
  renderChannels();
  renderRecordings();
  renderPlaylists();
}

async function loadData() {
  const [channels, recordings, playlists] = await Promise.all([
    api("/api/channels"),
    api("/api/recordings"),
    api("/api/playlists"),
  ]);
  state.channels = channels;
  state.recordings = recordings;
  state.playlists = playlists;
  render();
}

async function loadAll() {
  await loadData();
}

dom.loginForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const fd = new FormData(dom.loginForm);
  try {
    await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: fd.get("username"), password: fd.get("password") }),
    });
    await checkSession();
  } catch {
    alert("Login failed");
  }
});

dom.logoutBtn.addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  showAuthMode(false);
});

dom.addChannelForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const fd = new FormData(dom.addChannelForm);
  const autoAdd = fd.get("auto_add_to_playlist") === "on";
  const playlistValue = fd.get("auto_playlist_id");
  try {
    await api("/api/channels", {
      method: "POST",
      body: JSON.stringify({
        twitch_username: fd.get("twitch_username"),
        auto_add_to_playlist: autoAdd,
        auto_playlist_id: playlistValue ? Number(playlistValue) : null,
      }),
    });
    dom.addChannelForm.reset();
    await loadAll();
  } catch {
    alert("Unable to add channel");
  }
});

dom.createPlaylistForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const fd = new FormData(dom.createPlaylistForm);
  await api("/api/playlists", { method: "POST", body: JSON.stringify({ name: fd.get("name") }) });
  dom.createPlaylistForm.reset();
  await loadAll();
});

document.body.addEventListener("change", async (evt) => {
  const target = evt.target;
  const action = target.dataset.action;
  const channelId = Number(target.dataset.id);
  if (!action || !channelId) {
    return;
  }
  if (action === "toggleAuto") {
    const select = target.closest("tr").querySelector("select[data-action='updatePlaylist']");
    const playlistId = select ? select.value : "";
    await api(`/api/channels/${channelId}`, {
      method: "PATCH",
      body: JSON.stringify({
        auto_add_to_playlist: target.checked,
        auto_playlist_id: playlistId ? Number(playlistId) : null,
      }),
    });
    await loadAll();
  }
  if (action === "updatePlaylist") {
    const checkbox = target.closest("tr").querySelector("input[data-action='toggleAuto']");
    await api(`/api/channels/${channelId}`, {
      method: "PATCH",
      body: JSON.stringify({
        auto_add_to_playlist: checkbox.checked,
        auto_playlist_id: target.value ? Number(target.value) : null,
      }),
    });
    await loadAll();
  }
});

document.body.addEventListener("click", async (evt) => {
  const target = evt.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }
  const action = target.dataset.action;
  const id = Number(target.dataset.id);
  if (!action) {
    return;
  }

  if (action === "deleteChannel") {
    await api(`/api/channels/${id}`, { method: "DELETE" });
    await loadAll();
    return;
  }
  if (action === "rename") {
    const input = document.querySelector(`input[data-title="${id}"]`);
    await api(`/api/recordings/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title_display: input.value }),
    });
    await loadAll();
    return;
  }
  if (action === "share") {
    const input = document.querySelector(`input[data-slug="${id}"]`);
    const slug = input.value.trim();
    await api(`/api/recordings/${id}/share`, {
      method: "POST",
      body: JSON.stringify({
        share_slug: slug || null,
        share_enabled: true,
      }),
    });
    await loadAll();
    return;
  }
  if (action === "revoke") {
    await api(`/api/recordings/${id}/share`, { method: "DELETE" });
    await loadAll();
    return;
  }
  if (action === "addPlaylistItem") {
    const playlistId = Number(target.dataset.playlist);
    const select = document.querySelector(`select[data-playlist-recording="${playlistId}"]`);
    if (!select.value) return;
    await api(`/api/playlists/${playlistId}/items`, {
      method: "POST",
      body: JSON.stringify({ recording_id: Number(select.value), position: null }),
    });
    await loadAll();
    return;
  }
  if (action === "removePlaylistItem") {
    const playlistId = Number(target.dataset.playlist);
    const recordingId = Number(target.dataset.recording);
    await api(`/api/playlists/${playlistId}/items/${recordingId}`, { method: "DELETE" });
    await loadAll();
  }
});

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

setInterval(() => {
  if (dom.appSection.style.display === "block") {
    loadAll().catch(() => {});
  }
}, 20000);

checkSession();
