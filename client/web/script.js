"use strict";

/**
 * Мост между DOM и pywebview.api (см. client/ui_bridge/api.py).
 * Ждём событие `pywebviveready`, а не таймаут — момент, когда
 * window.pywebview.api реально становится доступен, гарантирован только им.
 */

function showScreen(id) {
  document.querySelectorAll(".screen").forEach((el) => el.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

function setAuthError(message) {
  const el = document.getElementById("auth-error");
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = message;
}

function switchAuthTab(tabName) {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panel === tabName);
  });
  setAuthError("");
}

function openPanel(id) {
  document.getElementById(id).classList.add("open");
  document.getElementById("overlay").classList.add("visible");
}

function closeAllPanels() {
  document.querySelectorAll(".side-panel").forEach((el) => el.classList.remove("open"));
  document.getElementById("overlay").classList.remove("visible");
}

function setStatus(text) {
  document.getElementById("status-text").textContent = text;
}

function setProgress(fraction) {
  const fill = document.getElementById("progress-fill");
  if (fraction === null || fraction === undefined) {
    fill.classList.add("indeterminate");
    fill.style.width = "";
    return;
  }
  fill.classList.remove("indeterminate");
  const pct = Math.max(0, Math.min(1, fraction)) * 100;
  fill.style.width = `${pct}%`;
}

function setPlayButtonBusy(isBusy) {
  const btn = document.getElementById("btn-play");
  btn.disabled = isBusy;
  btn.querySelector(".play-label").textContent = isBusy ? "ЗАГРУЗКА…" : "ИГРАТЬ";
}

// --- callbacks, вызываемые из ui_bridge/reporter.py через evaluate_js ---

window.onLauncherStatus = function onLauncherStatus(text) {
  setStatus(text);
};

window.onLauncherProgress = function onLauncherProgress(current, total) {
  if (!total) {
    setProgress(null);
    return;
  }
  setProgress(current / total);
};

// --- рендер списка опциональных модов ---

function renderMods(mods) {
  const list = document.getElementById("mods-list");
  list.innerHTML = "";

  if (!mods.length) {
    const empty = document.createElement("p");
    empty.className = "status-text";
    empty.textContent = "Опциональных модов пока нет";
    list.appendChild(empty);
    return;
  }

  for (const mod of mods) {
    const item = document.createElement("li");
    item.className = "mod-item";

    const info = document.createElement("div");
    const name = document.createElement("div");
    name.className = "mod-item-name";
    name.textContent = mod.name;
    info.appendChild(name);
    if (mod.description) {
      const desc = document.createElement("div");
      desc.className = "mod-item-desc";
      desc.textContent = mod.description;
      info.appendChild(desc);
    }

    const label = document.createElement("label");
    label.className = "switch";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(mod.enabled);
    checkbox.addEventListener("change", async () => {
      checkbox.disabled = true;
      try {
        await window.pywebview.api.toggle_optional_mod(mod.id, checkbox.checked);
      } finally {
        checkbox.disabled = false;
      }
    });
    const track = document.createElement("span");
    track.className = "switch-track";
    label.appendChild(checkbox);
    label.appendChild(track);

    item.appendChild(info);
    item.appendChild(label);
    list.appendChild(item);
  }
}

async function loadMods() {
  const result = await window.pywebview.api.get_optional_mods();
  if (result.ok) {
    renderMods(result.data);
  } else {
    setStatus(`Ошибка загрузки модов: ${result.error}`);
  }
}

// --- настройки ---

async function loadSettingsIntoPanel() {
  const settings = await window.pywebview.api.get_settings();
  document.getElementById("input-ram").value = settings.ram_mb;
  document.getElementById("ram-value").textContent = settings.ram_mb;
  document.getElementById("input-width").value = settings.resolution_width;
  document.getElementById("input-height").value = settings.resolution_height;
  document.getElementById("input-fullscreen").checked = Boolean(settings.fullscreen);
  document.getElementById("input-java-path").value = settings.java_path;
  document.getElementById("input-jvm-args").value = settings.jvm_arguments_extra;
  document.getElementById("input-game-args").value = settings.game_arguments_extra;
}

async function saveSettingsFromPanel() {
  const payload = {
    ram_mb: Number(document.getElementById("input-ram").value),
    resolution_width: Number(document.getElementById("input-width").value),
    resolution_height: Number(document.getElementById("input-height").value),
    fullscreen: document.getElementById("input-fullscreen").checked,
    java_path: document.getElementById("input-java-path").value.trim(),
    jvm_arguments_extra: document.getElementById("input-jvm-args").value.trim(),
    game_arguments_extra: document.getElementById("input-game-args").value.trim(),
  };
  await window.pywebview.api.save_settings(payload);
  closeAllPanels();
}

// --- инициализация после готовности pywebview.api ---

function initEventHandlers() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => switchAuthTab(btn.dataset.tab));
  });

  document.getElementById("form-login").addEventListener("submit", async (event) => {
    event.preventDefault();
    setAuthError("");
    const form = event.target;
    const username = form.username.value.trim();
    const password = form.password.value;
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    try {
      const result = await window.pywebview.api.login(username, password);
      if (result.ok) {
        enterMainScreen(result.data.username);
      } else {
        setAuthError(result.error);
      }
    } finally {
      submitBtn.disabled = false;
    }
  });

  document.getElementById("form-register").addEventListener("submit", async (event) => {
    event.preventDefault();
    setAuthError("");
    const form = event.target;
    const username = form.username.value.trim();
    const password = form.password.value;
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    try {
      const result = await window.pywebview.api.register(username, password);
      if (result.ok) {
        const loginResult = await window.pywebview.api.login(username, password);
        if (loginResult.ok) {
          enterMainScreen(loginResult.data.username);
          return;
        }
        setAuthError(loginResult.error);
      } else {
        setAuthError(result.error);
      }
    } finally {
      submitBtn.disabled = false;
    }
  });

  document.getElementById("btn-logout").addEventListener("click", async () => {
    await window.pywebview.api.logout();
    setAuthError("");
    document.getElementById("form-login").reset();
    document.getElementById("form-register").reset();
    switchAuthTab("login");
    showScreen("screen-auth");
  });

  document.getElementById("btn-settings").addEventListener("click", async () => {
    await loadSettingsIntoPanel();
    openPanel("panel-settings");
  });

  document.getElementById("btn-mods").addEventListener("click", async () => {
    await loadMods();
    openPanel("panel-mods");
  });

  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", closeAllPanels);
  });
  document.getElementById("overlay").addEventListener("click", closeAllPanels);

  document.getElementById("input-ram").addEventListener("input", (event) => {
    document.getElementById("ram-value").textContent = event.target.value;
  });

  document.getElementById("btn-save-settings").addEventListener("click", saveSettingsFromPanel);

  document.getElementById("btn-browse-java").addEventListener("click", async () => {
    const path = await window.pywebview.api.browse_java_path();
    if (path) {
      document.getElementById("input-java-path").value = path;
    }
  });

  document.getElementById("btn-play").addEventListener("click", async () => {
    setPlayButtonBusy(true);
    setProgress(0);
    setStatus("Подготовка…");
    const result = await window.pywebview.api.play();
    if (!result.ok) {
      setStatus(`Ошибка: ${result.error}`);
      setPlayButtonBusy(false);
    }
    // При успехе кнопку разблокируем по завершении/ошибке —
    // финальный статус придёт через onLauncherStatus из фонового потока.
  });
}

function enterMainScreen(username) {
  document.getElementById("current-username").textContent = username;
  setStatus("Готово к запуску");
  setProgress(0);
  document.getElementById("progress-fill").style.width = "0%";
  setPlayButtonBusy(false);
  showScreen("screen-main");
}

let pendingUpdateUrl = null;
let pendingUpdaterUrl = null;

async function checkForUpdate() {
  const result = await window.pywebview.api.check_for_update();
  if (!result.ok || !result.update_available) {
    return;
  }
  pendingUpdateUrl = result.download_url;
  pendingUpdaterUrl = result.updater_url;
  document.getElementById("update-banner-text").textContent = `Доступна версия ${result.version}`;
  document.getElementById("update-banner").hidden = false;
}

function initUpdateBanner() {
  document.getElementById("btn-update-later").addEventListener("click", () => {
    document.getElementById("update-banner").hidden = true;
  });

  document.getElementById("btn-update-now").addEventListener("click", async (event) => {
    if (!pendingUpdateUrl || !pendingUpdaterUrl) return;
    event.target.disabled = true;
    const result = await window.pywebview.api.start_update(pendingUpdateUrl, pendingUpdaterUrl);
    if (!result.ok) {
      event.target.disabled = false;
      setAuthError(result.error);
    }
  });
}

async function bootstrap() {
  initEventHandlers();
  initUpdateBanner();
  checkForUpdate();

  const session = await window.pywebview.api.get_session();
  if (session) {
    enterMainScreen(session.username);
  } else {
    showScreen("screen-auth");
  }
}

window.addEventListener("pywebviewready", bootstrap);
