const TOKEN_KEY = "mclauncher_admin_token";

function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

async function api(path, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const resp = await fetch(`/api/v1${path}`, { ...options, headers });
  if (resp.status === 401) {
    clearToken();
    showScreen("login");
    throw new Error("Сессия истекла, войдите заново");
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch {
      // тело не JSON — оставляем HTTP-статус как есть
    }
    throw new Error(detail);
  }
  if (resp.status === 204) {
    return null;
  }
  return resp.json();
}

function showScreen(name) {
  document.getElementById("screen-login").hidden = name !== "login";
  document.getElementById("screen-main").hidden = name !== "main";
}

async function loadProfile() {
  const status = document.getElementById("profile-status");
  status.textContent = "";
  try {
    const profile = await api("/admin/profile");
    document.getElementById("profile-mc_version").value = profile.mc_version;
    document.getElementById("profile-loader").value = profile.loader;
    document.getElementById("profile-loader_version").value = profile.loader_version || "";
    document.getElementById("profile-server_address").value = profile.server_address;
    document.getElementById("profile-server_port").value = profile.server_port;
  } catch (err) {
    // Профиль ещё не задан ни разу — 404, форма просто остаётся пустой.
    status.textContent = err.message.includes("404") ? "" : `Ошибка: ${err.message}`;
  }
}

async function loadMods() {
  const tbody = document.getElementById("mods-tbody");
  const status = document.getElementById("mods-status");
  status.textContent = "Загрузка…";
  try {
    const mods = await api("/admin/mods");
    tbody.innerHTML = "";
    for (const mod of mods) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(mod.name)}</td>
        <td>${escapeHtml(mod.mod_type)}</td>
        <td>${escapeHtml(mod.loader)}</td>
        <td>${escapeHtml(mod.mc_version)}</td>
        <td>${formatSize(mod.size)}</td>
        <td></td>
      `;
      const deleteCell = tr.lastElementChild;
      const deleteBtn = document.createElement("button");
      deleteBtn.className = "btn btn-danger";
      deleteBtn.textContent = "Удалить";
      deleteBtn.addEventListener("click", () => deleteMod(mod.id, mod.name));
      deleteCell.appendChild(deleteBtn);
      tbody.appendChild(tr);
    }
    status.textContent = mods.length ? "" : "Модов пока нет";
  } catch (err) {
    status.textContent = `Ошибка: ${err.message}`;
  }
}

async function deleteMod(id, name) {
  if (!confirm(`Удалить мод "${name}"?`)) {
    return;
  }
  try {
    await api(`/admin/mods/${id}`, { method: "DELETE" });
    await loadMods();
  } catch (err) {
    document.getElementById("mods-status").textContent = `Ошибка: ${err.message}`;
  }
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} КБ`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

function init() {
  document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = document.getElementById("login-password").value;
    const errorEl = document.getElementById("login-error");
    errorEl.hidden = true;
    try {
      const resp = await fetch("/api/v1/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!resp.ok) {
        throw new Error("Неверный пароль");
      }
      const data = await resp.json();
      setToken(data.access_token);
      await enterMainScreen();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });

  document.getElementById("btn-logout").addEventListener("click", () => {
    clearToken();
    showScreen("login");
  });

  document.getElementById("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("profile-status");
    status.textContent = "Сохранение…";
    const loaderVersion = document.getElementById("profile-loader_version").value.trim();
    const payload = {
      mc_version: document.getElementById("profile-mc_version").value.trim(),
      loader: document.getElementById("profile-loader").value,
      loader_version: loaderVersion || null,
      server_address: document.getElementById("profile-server_address").value.trim(),
      server_port: Number(document.getElementById("profile-server_port").value),
    };
    try {
      await api("/admin/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      status.textContent = "Сохранено";
    } catch (err) {
      status.textContent = `Ошибка: ${err.message}`;
    }
  });

  document.getElementById("mod-upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("mod-upload-status");
    const fileInput = document.getElementById("mod-file");
    const file = fileInput.files[0];
    if (!file) {
      status.textContent = "Выберите файл";
      return;
    }
    const form = new FormData();
    form.append("name", document.getElementById("mod-name").value.trim());
    form.append("description", document.getElementById("mod-description").value.trim());
    form.append("mod_type", document.getElementById("mod-type").value);
    form.append("loader", document.getElementById("mod-loader").value.trim());
    form.append("mc_version", document.getElementById("mod-mc_version").value.trim());
    form.append("file", file);

    status.textContent = "Загрузка…";
    try {
      await api("/admin/mods", { method: "POST", body: form });
      status.textContent = "Загружено";
      event.target.reset();
      await loadMods();
    } catch (err) {
      status.textContent = `Ошибка: ${err.message}`;
    }
  });

  if (getToken()) {
    enterMainScreen();
  } else {
    showScreen("login");
  }
}

async function enterMainScreen() {
  showScreen("main");
  await loadProfile();
  await loadMods();
}

init();
