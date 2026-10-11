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
  const app = document.getElementById("app");
  if (fraction === null || fraction === undefined) {
    fill.classList.add("indeterminate");
    fill.style.width = "";
    if (playButtonBusy) renderPlayLabel(null);
    return;
  }
  fill.classList.remove("indeterminate");
  const clamped = Math.max(0, Math.min(1, fraction));
  fill.style.width = `${clamped * 100}%`;
  app.style.setProperty("--p", clamped);
  if (playButtonBusy) renderPlayLabel(clamped);
}

// Прогресс загрузки дублируется крупно на самой кнопке, пока она занята.
let playButtonBusy = false;
let gameInstalled = true;
// Пока процесс игры жив, PLAY превращается в KILL (принудительное закрытие).
let gameRunning = false;

function renderPlayLabel(fraction) {
  const label = document.querySelector("#btn-play .play-label");
  if (gameRunning) {
    label.textContent = "KILL";
  } else if (playButtonBusy) {
    label.textContent = fraction == null ? "…" : `${Math.round(fraction * 100)}%`;
  } else {
    label.textContent = gameInstalled ? "PLAY" : "INSTALL";
  }
}

function setPlayButtonBusy(isBusy) {
  playButtonBusy = isBusy;
  document.getElementById("btn-play").disabled = isBusy && !gameRunning;
  document.getElementById("btn-reinstall").disabled = isBusy || gameRunning;
  renderPlayLabel(0);
}

function setGameRunning(running) {
  gameRunning = running;
  document.querySelector(".play-slot").dataset.mode = running ? "kill" : gameInstalled ? "play" : "install";
  setPlayButtonBusy(false);
}

const LOADER_NAMES = { forge: "Forge", neoforge: "NeoForge", fabric: "Fabric", quilt: "Quilt" };

async function loadProfileInfo() {
  const result = await window.pywebview.api.get_profile();
  const box = document.getElementById("profile-info");
  if (!result.ok) {
    box.hidden = true;
    return;
  }
  const p = result.profile;
  const loader = LOADER_NAMES[p.loader];
  const build = `Minecraft ${p.mc_version}`;
  document.getElementById("profile-build").textContent = loader
    ? `${build} + ${loader}${p.loader_version ? ` ${p.loader_version}` : ""}`
    : build;
  document.getElementById("profile-server").textContent =
    p.server_port === 25565 ? p.server_address : `${p.server_address}:${p.server_port}`;
  box.hidden = false;
}

async function refreshInstallState() {
  gameInstalled = await window.pywebview.api.is_installed();
  if (!gameRunning) {
    document.querySelector(".play-slot").dataset.mode = gameInstalled ? "play" : "install";
  }
  renderPlayLabel(0);
}

// --- callbacks, вызываемые из ui_bridge/reporter.py через evaluate_js ---

window.onLauncherStatus = function onLauncherStatus(text) {
  setStatus(text);
  // Ошибка подготовки — фоновый поток завершился, игра не запустилась.
  if (text.startsWith("Ошибка")) {
    setPlayButtonBusy(false);
    refreshInstallState();
    loadProfileInfo();
  }
};

window.onGameState = function onGameState(running, text) {
  setStatus(text);
  setProgress(running ? 1 : 0);
  setGameRunning(running);
  if (!running) {
    refreshInstallState();
    loadProfileInfo();
  }
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

// --- скин и плащ ---

// Развёртка скина: [srcX, srcY, w, h, dstX, dstY] в пикселях 64-px скина;
// превью — вид спереди 16x32. Старый 64x32 не имеет левых рук/ног и
// второго слоя на теле — для них зеркалим правые конечности.
const SKIN_BASE = [
  [8, 8, 8, 8, 4, 0],    // голова
  [20, 20, 8, 12, 4, 8], // тело
  [44, 20, 4, 12, 0, 8], // правая рука
  [4, 20, 4, 12, 4, 20], // правая нога
];
const SKIN_LEFT_LIMBS = [
  [36, 52, 4, 12, 12, 8], // левая рука
  [20, 52, 4, 12, 8, 20], // левая нога
];
const SKIN_OVERLAY_LEGACY = [[40, 8, 8, 8, 4, 0]]; // шапка
const SKIN_OVERLAY_MODERN = [
  [20, 36, 8, 12, 4, 8],  // куртка
  [44, 36, 4, 12, 0, 8],  // правый рукав
  [52, 52, 4, 12, 12, 8], // левый рукав
  [4, 36, 4, 12, 4, 20],  // правая штанина
  [4, 52, 4, 12, 8, 20],  // левая штанина
];

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function drawParts(ctx, img, parts, scale) {
  for (const [sx, sy, w, h, dx, dy] of parts) {
    ctx.drawImage(img, sx * scale, sy * scale, w * scale, h * scale, dx, dy, w, h);
  }
}

function drawMirrored(ctx, img, [sx, sy, w, h], dx, dy, scale) {
  ctx.save();
  ctx.translate(dx + w, dy);
  ctx.scale(-1, 1);
  ctx.drawImage(img, sx * scale, sy * scale, w * scale, h * scale, 0, 0, w, h);
  ctx.restore();
}

// Голова Стива по пикселям — когда у игрока нет своего скина.
const STEVE_FACE = [
  "hhhhhhhh",
  "hhhhhhhh",
  "hssssssh",
  "ssssssss",
  "swbssbws",
  "sssnnsss",
  "ssmssmss",
  "ssmmmmss",
];
const STEVE_COLORS = { h: "#3b2716", s: "#b98a6c", n: "#94634a", w: "#ffffff", b: "#4a3b8f", m: "#6b3e2e" };

async function renderUserHead(dataUrl) {
  const canvas = document.getElementById("user-head");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, 8, 8);
  if (!dataUrl) {
    STEVE_FACE.forEach((row, y) => [...row].forEach((c, x) => {
      ctx.fillStyle = STEVE_COLORS[c];
      ctx.fillRect(x, y, 1, 1);
    }));
    return;
  }
  const img = await loadImage(dataUrl);
  const scale = img.width / 64;
  // лицо (8,8) и поверх — слой шапки/волос (40,8), как в игре
  ctx.drawImage(img, 8 * scale, 8 * scale, 8 * scale, 8 * scale, 0, 0, 8, 8);
  ctx.drawImage(img, 40 * scale, 8 * scale, 8 * scale, 8 * scale, 0, 0, 8, 8);
}

async function loadUserHead() {
  await renderUserHead(null);
  const result = await window.pywebview.api.get_textures();
  if (result.ok) await renderUserHead(result.data.skin);
}

async function renderSkinPreview(dataUrl) {
  const canvas = document.getElementById("skin-preview");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  document.getElementById("skin-caption").textContent = dataUrl ? "Скин" : "Скин не загружен";
  document.getElementById("btn-delete-skin").hidden = !dataUrl;
  renderUserHead(dataUrl);
  if (!dataUrl) return;

  const img = await loadImage(dataUrl);
  const scale = img.width / 64;
  const isLegacy = img.height * 2 === img.width;
  drawParts(ctx, img, SKIN_BASE, scale);
  if (isLegacy) {
    drawMirrored(ctx, img, [44, 20, 4, 12], 12, 8, scale);
    drawMirrored(ctx, img, [4, 20, 4, 12], 8, 20, scale);
  } else {
    drawParts(ctx, img, SKIN_LEFT_LIMBS, scale);
    drawParts(ctx, img, SKIN_OVERLAY_MODERN, scale);
  }
  drawParts(ctx, img, SKIN_OVERLAY_LEGACY, scale);
}

async function renderCapePreview(dataUrl) {
  const canvas = document.getElementById("cape-preview");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  document.getElementById("cape-caption").textContent = dataUrl ? "Плащ" : "Плащ не загружен";
  document.getElementById("btn-delete-cape").hidden = !dataUrl;
  if (!dataUrl) return;

  const img = await loadImage(dataUrl);
  // Старые 22x17 плащи лежат в той же раскладке, что и 64x32, только без
  // запаса по краям — масштаб считаем от ширины 64 в обоих случаях.
  const scale = img.width === 22 ? 1 : img.width / 64;
  ctx.drawImage(img, 1 * scale, 1 * scale, 10 * scale, 16 * scale, 0, 0, 10, 16);
}

function setTextureStatus(text) {
  document.getElementById("texture-status").textContent = text;
}

async function loadTextures() {
  setTextureStatus("Загрузка…");
  const result = await window.pywebview.api.get_textures();
  if (!result.ok) {
    setTextureStatus(`Ошибка: ${result.error}`);
    return;
  }
  setTextureStatus("");
  await renderSkinPreview(result.data.skin);
  await renderCapePreview(result.data.cape);
}

async function uploadTexture(kind, button) {
  button.disabled = true;
  setTextureStatus("");
  try {
    const result = await window.pywebview.api.upload_texture(kind);
    if (!result.ok) {
      setTextureStatus(`Ошибка: ${result.error}`);
      return;
    }
    if (result.cancelled) return;
    if (kind === "skin") {
      await renderSkinPreview(result.data_url);
      setTextureStatus("Скин обновлён");
    } else {
      await renderCapePreview(result.data_url);
      setTextureStatus("Плащ обновлён");
    }
  } finally {
    button.disabled = false;
  }
}

const TEXTURE_RENDERERS = { skin: renderSkinPreview, cape: renderCapePreview };
const TEXTURE_NAMES = { skin: "скин", cape: "плащ" };

async function deleteTexture(kind, button) {
  if (!confirm(`Удалить ${TEXTURE_NAMES[kind]}?`)) return;
  button.disabled = true;
  setTextureStatus("");
  try {
    const result = await window.pywebview.api.delete_texture(kind);
    if (!result.ok) {
      setTextureStatus(`Ошибка: ${result.error}`);
      return;
    }
    await TEXTURE_RENDERERS[kind](null);
    setTextureStatus(kind === "skin" ? "Скин удалён" : "Плащ удалён");
  } finally {
    button.disabled = false;
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
  document.getElementById("input-debug").checked = Boolean(settings.debug);
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
    debug: document.getElementById("input-debug").checked,
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

  document.getElementById("btn-skin").addEventListener("click", async () => {
    openPanel("panel-skin");
    await loadTextures();
  });

  document.getElementById("btn-upload-skin").addEventListener("click", (event) => {
    uploadTexture("skin", event.currentTarget);
  });

  document.getElementById("btn-upload-cape").addEventListener("click", (event) => {
    uploadTexture("cape", event.currentTarget);
  });

  document.getElementById("btn-delete-skin").addEventListener("click", (event) => {
    deleteTexture("skin", event.currentTarget);
  });

  document.getElementById("btn-delete-cape").addEventListener("click", (event) => {
    deleteTexture("cape", event.currentTarget);
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
    if (gameRunning) {
      if (!confirm("Принудительно закрыть игру? Несохранённый прогресс может потеряться.")) return;
      const result = await window.pywebview.api.kill_game();
      if (!result.ok) setStatus(`Ошибка: ${result.error}`);
      // Кнопка вернётся в PLAY через onGameState, когда процесс завершится.
      return;
    }
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

  document.getElementById("btn-folder").addEventListener("click", async () => {
    const result = await window.pywebview.api.open_game_folder();
    if (!result.ok) setStatus(`Ошибка: ${result.error}`);
  });

  document.getElementById("btn-reinstall").addEventListener("click", async () => {
    if (!confirm("Удалить и заново установить папку игры? Все локальные изменения в ней будут потеряны.")) {
      return;
    }
    setPlayButtonBusy(true);
    setProgress(0);
    setStatus("Переустановка…");
    const result = await window.pywebview.api.reinstall();
    if (!result.ok) {
      setStatus(`Ошибка: ${result.error}`);
      setPlayButtonBusy(false);
    }
    // Как и play() — финальный статус придёт через onLauncherStatus.
  });
}

async function enterMainScreen(username) {
  document.getElementById("current-username").textContent = username;
  setStatus("Готово к запуску");
  setProgress(0);
  document.getElementById("progress-fill").style.width = "0%";
  // Страница могла перезагрузиться, пока игра запущена — восстанавливаем состояние.
  const state = await window.pywebview.api.get_game_state();
  setGameRunning(state.running);
  if (state.busy && !state.running) setPlayButtonBusy(true);
  if (state.running) setStatus("Игра запущена");
  refreshInstallState();
  loadProfileInfo();
  loadUserHead();
  showScreen("screen-main");

  const version = await window.pywebview.api.get_launcher_version();
  document.getElementById("launcher-version").textContent = version;
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
