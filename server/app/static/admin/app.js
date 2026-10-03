const TOKEN_KEY = "mclauncher_admin_token";
const $ = (id) => document.getElementById(id);

const state = {
  profile: null, // null — профиль ещё не задан
  mods: [],
  authlib: [],
  launcher: null,
};

// --- утилиты ---------------------------------------------------------------

function getToken() { return sessionStorage.getItem(TOKEN_KEY); }
function setToken(token) { sessionStorage.setItem(TOKEN_KEY, token); }
function clearToken() { sessionStorage.removeItem(TOKEN_KEY); }

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child != null) node.append(child);
  }
  return node;
}

function toast(message, isError = false) {
  const node = el("div", { class: isError ? "toast err" : "toast", text: message });
  $("toasts").append(node);
  setTimeout(() => node.remove(), isError ? 7000 : 3500);
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

function plural(n, one, few, many) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}

async function api(path, options = {}, { auth = true } = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (auth && token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(`/api/v1${path}`, { ...options, headers });
  if (resp.status === 401 && auth) {
    clearToken();
    showScreen("login");
    throw new Error("Сессия истекла, войдите заново");
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg).join("; ");
    } catch { /* тело не JSON — оставляем статус */ }
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }
  return resp.status === 204 ? null : resp.json();
}

function showScreen(name) {
  $("screen-login").hidden = name !== "login";
  $("screen-main").hidden = name !== "main";
}

// --- данные ----------------------------------------------------------------

async function loadProfile() {
  try {
    state.profile = await api("/admin/profile");
  } catch (err) {
    if (err.status !== 404) throw err;
    state.profile = null;
  }
}

async function loadMods() {
  state.mods = await api("/admin/mods");
}

async function loadExtras() {
  // публичные эндпоинты: падение одного не должно ломать остальную админку
  state.authlib = await api("/launcher/authlib-jars", {}, { auth: false }).catch(() => null);
  state.launcher = await api("/launcher/version", {}, { auth: false }).catch(() => null);
}

async function refreshAll() {
  await Promise.all([loadProfile(), loadMods(), loadExtras()]);
  renderAll();
}

function matchesProfile(mod) {
  const p = state.profile;
  return !!p && mod.loader.toLowerCase() === p.loader.toLowerCase() && mod.mc_version === p.mc_version;
}

// --- рендер ----------------------------------------------------------------

function renderAll() {
  renderStrip();
  renderOverview();
  renderMods();
  fillProfileForm();
  const forProfile = state.mods.filter(matchesProfile).length;
  $("nav-mods-count").textContent = state.mods.length ? String(forProfile) : "";
}

function renderStrip() {
  const strip = $("profile-strip");
  strip.replaceChildren();
  const p = state.profile;
  if (!p) {
    strip.append(
      el("span", { text: "Профиль сервера не задан" }),
      el("a", { href: "#/server", text: "Задать профиль" }),
    );
    return;
  }
  const build = `${p.loader} ${p.mc_version}${p.loader_version ? ` (${p.loader_version})` : ""}`;
  strip.append(
    el("span", { class: "tag", text: build }),
    el("span", { class: "sep", text: "→" }),
    el("span", { text: `${p.server_address}:${p.server_port}` }),
  );
}

function renderOverview() {
  const list = $("checks");
  list.replaceChildren();
  const p = state.profile;
  const forProfile = state.mods.filter(matchesProfile);
  const required = forProfile.filter((m) => m.mod_type === "required");

  const checks = [];

  checks.push(p
    ? { level: "ok", title: "Профиль сервера задан", detail: `${p.loader} ${p.mc_version}, ${p.server_address}:${p.server_port}`, link: ["#/server", "Изменить"] }
    : { level: "bad", title: "Профиль сервера не задан", detail: "Без него лаунчер не знает, какую версию ставить и куда подключаться.", link: ["#/server", "Задать"] });

  if (p) {
    if (p.loader === "vanilla") {
      checks.push({ level: "ok", title: "Моды не нужны", detail: "Профиль vanilla — лаунчер ставит игру без модов." });
    } else if (required.length) {
      const optional = forProfile.length - required.length;
      checks.push({ level: "ok", title: `Обязательных модов: ${required.length}`, detail: `Необязательных: ${optional}`, link: ["#/mods", "Открыть"] });
    } else {
      const other = state.mods.length - forProfile.length;
      checks.push({
        level: "warn",
        title: "Для этого профиля нет обязательных модов",
        detail: other ? `Загружено модов для других версий: ${other}.` : "Игроки зайдут без модов.",
        link: ["#/mods", "Добавить"],
      });
    }
  }

  if (state.authlib === null) {
    checks.push({ level: "warn", title: "Не удалось получить список authlib", detail: "Запрос /launcher/authlib-jars завершился ошибкой." });
  } else if (state.authlib.length) {
    checks.push({ level: "ok", title: "Скины и вход через свой бэкенд", detail: `Доступные версии authlib: ${state.authlib.map((j) => j.version).join(", ")}` });
  } else {
    checks.push({ level: "warn", title: "Нет пропатченных authlib", detail: "Положите authlib-<версия>_skinfix.jar в storage/authlib — без них клиенты не смогут войти через этот бэкенд." });
  }

  if (state.launcher === null) {
    checks.push({ level: "warn", title: "Не удалось проверить релиз лаунчера", detail: "Бэкенд не достучался до GitHub." });
  } else if (state.launcher.version) {
    checks.push({ level: "ok", title: `Релиз лаунчера: ${state.launcher.version}`, detail: "Клиенты предложат обновиться, если у них версия старее." });
  } else {
    checks.push({ level: "warn", title: "Релиз лаунчера не найден", detail: "Проверьте LAUNCHER_GITHUB_REPO в .env и наличие релиза на GitHub." });
  }

  for (const c of checks) {
    list.append(el("li", {},
      el("span", { class: `dot ${c.level}`, "aria-hidden": "true" }),
      el("div", {}, el("div", { class: "title", text: c.title }), el("div", { class: "detail", text: c.detail })),
      c.link ? el("a", { href: c.link[0], text: c.link[1] }) : null,
    ));
  }
}

function renderMods() {
  const root = $("mods-list");
  root.replaceChildren();
  const query = $("mods-search").value.trim().toLowerCase();
  const showAll = $("mods-all-versions").checked;

  const visible = state.mods.filter((m) =>
    (showAll || matchesProfile(m)) &&
    (!query || m.name.toLowerCase().includes(query) || m.file_name.toLowerCase().includes(query)));

  if (!visible.length) {
    const hiddenOther = !showAll && state.mods.length;
    root.append(el("div", { class: "empty" },
      el("p", { text: query ? "Ничего не найдено" : hiddenOther ? "Для текущего профиля модов нет" : "Модов пока нет" }),
      el("p", { class: "small", text: hiddenOther && !query ? `Загружено для других версий: ${state.mods.length}. Включите «Показать и другие версии».` : "Загрузите jar-файлы — лаунчер скачает их игрокам." }),
      query ? null : el("button", { class: "btn btn-primary", type: "button", text: "Добавить моды", onclick: openAddDialog }),
    ));
    return;
  }

  const groups = [
    ["required", "Обязательные", "Скачиваются всем игрокам, лишние моды в папке удаляются."],
    ["optional", "Необязательные", "Игрок сам включает нужные в лаунчере."],
  ];
  for (const [type, title, hint] of groups) {
    const items = visible.filter((m) => m.mod_type === type);
    if (!items.length) continue;
    root.append(
      el("div", { class: "group-title" }, el("h2", { text: title }), el("span", { class: "count", text: String(items.length) })),
      el("p", { class: "group-hint", text: hint }),
      ...items.map(modRow),
    );
  }
}

function modRow(mod) {
  const other = !matchesProfile(mod);
  const nameEl = el("div", { class: "name" }, mod.name, other ? el("span", { class: "badge", text: "другая версия" }) : null);
  return el("div", { class: other ? "mod other" : "mod" },
    el("div", {}, nameEl, el("div", { class: "file", text: mod.file_name })),
    el("div", { class: "meta", text: `${mod.loader} ${mod.mc_version} · ${formatSize(mod.size)}` }),
    el("div", { class: "actions" },
      el("button", { class: "btn btn-sm", type: "button", text: "Изменить", onclick: () => openEdit(mod) }),
      el("button", { class: "btn btn-danger btn-sm", type: "button", text: "Удалить", onclick: () => askDelete(mod) }),
    ),
    mod.description ? el("div", { class: "desc", text: mod.description }) : null,
  );
}

// --- удаление мода ---------------------------------------------------------

function askDelete(mod) {
  const dlg = $("dlg-delete");
  $("delete-text").textContent = `«${mod.name}» (${mod.file_name})`;
  dlg.returnValue = "";
  dlg.onclose = async () => {
    if (dlg.returnValue !== "confirm") return;
    try {
      await api(`/admin/mods/${mod.id}`, { method: "DELETE" });
      toast(`Удалён: ${mod.name}`);
      await loadMods();
      renderAll();
    } catch (err) {
      toast(err.message, true);
    }
  };
  dlg.showModal();
}

// --- редактирование мода ---------------------------------------------------

let editing = null; // {mod, type}

function editValues() {
  return {
    name: $("edit-name").value.trim(),
    description: $("edit-description").value.trim() || null,
    mod_type: editing.type,
    loader: $("edit-loader").value.trim(),
    mc_version: $("edit-mc_version").value.trim(),
  };
}

function editChanges() {
  const values = editValues();
  const mod = editing.mod;
  const changes = {};
  for (const key of Object.keys(values)) {
    if (values[key] !== (mod[key] ?? null)) changes[key] = values[key];
  }
  return changes;
}

function syncEdit() {
  for (const btn of $("edit-type").querySelectorAll("button")) {
    btn.setAttribute("aria-pressed", String(btn.dataset.type === editing.type));
  }
  const v = editValues();
  $("edit-save").disabled = !(v.name && v.loader && v.mc_version && Object.keys(editChanges()).length);
}

function openEdit(mod) {
  editing = { mod, type: mod.mod_type };
  $("edit-file").textContent = mod.file_name;
  $("edit-name").value = mod.name;
  $("edit-description").value = mod.description || "";
  $("edit-loader").value = mod.loader;
  $("edit-mc_version").value = mod.mc_version;
  syncEdit();
  $("dlg-edit").showModal();
}

async function saveEdit(event) {
  event.preventDefault();
  const changes = editChanges();
  if (!Object.keys(changes).length) return;
  $("edit-save").disabled = true;
  try {
    await api(`/admin/mods/${editing.mod.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    });
    $("dlg-edit").close();
    toast(`Сохранено: ${changes.name ?? editing.mod.name}`);
    await loadMods();
    renderAll();
  } catch (err) {
    toast(err.message, true);
    syncEdit();
  }
}

// --- добавление модов ------------------------------------------------------

let queue = []; // {file, name, description, type, status: "idle"|"busy"|"ok"|"err", error}
let bulkType = "required";

function guessName(fileName) {
  let base = fileName.replace(/\.jar$/i, "");
  base = base.replace(/[-_+ ]v?\d.*$/, "") || base;
  base = base.replace(/[-_]+/g, " ").trim();
  return base ? base[0].toUpperCase() + base.slice(1) : fileName;
}

function openAddDialog() {
  queue = [];
  bulkType = "required";
  $("add-loader").value = state.profile?.loader && state.profile.loader !== "vanilla" ? state.profile.loader : (state.profile ? "forge" : "");
  $("add-mc_version").value = state.profile?.mc_version || "";
  syncBulkType();
  renderQueue();
  $("dlg-add").showModal();
}

function addFiles(fileList) {
  for (const file of fileList) {
    if (!/\.jar$/i.test(file.name)) {
      toast(`${file.name}: нужен файл .jar`, true);
      continue;
    }
    if (queue.some((q) => q.file.name === file.name && q.file.size === file.size)) continue;
    queue.push({ file, name: guessName(file.name), description: "", type: bulkType, status: "idle", error: "" });
  }
  renderQueue();
}

function syncBulkType() {
  for (const btn of $("add-type-all").querySelectorAll("button")) {
    btn.setAttribute("aria-pressed", String(btn.dataset.type === bulkType));
  }
}

function typeToggle(item) {
  const wrap = el("div", { class: "segmented", role: "group", "aria-label": "Тип мода" });
  for (const [value, label] of [["required", "Обязательный"], ["optional", "Необязательный"]]) {
    wrap.append(el("button", {
      type: "button", "aria-pressed": String(item.type === value), text: label,
      onclick: () => { item.type = value; renderQueue(); },
    }));
  }
  return wrap;
}

function renderQueue() {
  const list = $("add-queue");
  list.replaceChildren();
  $("add-defaults").hidden = !queue.length;

  for (const item of queue) {
    const locked = item.status === "busy" || item.status === "ok";
    const nameInput = el("input", {
      type: "text", value: item.name, "aria-label": `Название для ${item.file.name}`,
      oninput: (e) => { item.name = e.target.value; updateSubmit(); },
    });
    const descInput = el("input", {
      type: "text", value: item.description, placeholder: "Описание (необязательно)", "aria-label": `Описание для ${item.file.name}`,
      oninput: (e) => { item.description = e.target.value; },
    });
    nameInput.disabled = descInput.disabled = locked;

    const li = el("li", {},
      nameInput,
      locked ? el("span") : typeToggle(item),
      locked ? el("span") : el("button", {
        class: "btn btn-ghost btn-sm", type: "button", text: "Убрать",
        onclick: () => { queue.splice(queue.indexOf(item), 1); renderQueue(); },
      }),
      el("div", { class: "q-desc", style: "grid-column: 1 / -1" }, descInput),
      el("div", { class: "q-file", text: `${item.file.name} · ${formatSize(item.file.size)}` }),
    );
    if (item.status === "busy") li.append(el("div", { class: "q-state", text: "Загрузка…" }));
    if (item.status === "ok") li.append(el("div", { class: "q-state ok", text: "Загружено" }));
    if (item.status === "err") li.append(el("div", { class: "q-state err", text: item.error }));
    list.append(li);
  }
  updateSubmit();
}

function pending() {
  return queue.filter((q) => q.status === "idle" || q.status === "err");
}

function updateSubmit() {
  const todo = pending();
  const valid = todo.length && todo.every((q) => q.name.trim());
  $("add-submit").disabled = !valid || queue.some((q) => q.status === "busy");
  $("add-submit").textContent = todo.length > 1 ? `Загрузить (${todo.length})` : "Загрузить";
  $("add-summary").textContent = queue.length
    ? `${queue.length} ${plural(queue.length, "файл", "файла", "файлов")} · ${$("add-loader").value || "?"} ${$("add-mc_version").value || "?"}`
    : "";
}

async function submitUpload() {
  const loader = $("add-loader").value.trim();
  const mcVersion = $("add-mc_version").value.trim();
  if (!loader || !mcVersion) {
    toast("Укажите загрузчик и версию Minecraft", true);
    return;
  }
  $("add-submit").disabled = true;
  for (const item of pending()) {
    item.status = "busy";
    renderQueue();
    const form = new FormData();
    form.append("name", item.name.trim());
    if (item.description.trim()) form.append("description", item.description.trim());
    form.append("mod_type", item.type);
    form.append("loader", loader);
    form.append("mc_version", mcVersion);
    form.append("file", item.file);
    try {
      await api("/admin/mods", { method: "POST", body: form });
      item.status = "ok";
    } catch (err) {
      item.status = "err";
      item.error = err.message;
    }
    renderQueue();
  }
  const done = queue.filter((q) => q.status === "ok").length;
  const failed = queue.filter((q) => q.status === "err").length;
  await loadMods();
  renderAll();
  if (!failed) {
    $("dlg-add").close();
    toast(`Загружено: ${done}`);
  } else {
    toast(`Загружено: ${done}, с ошибкой: ${failed}`, true);
  }
}

// --- профиль сервера -------------------------------------------------------

const PROFILE_FIELDS = ["mc_version", "loader", "loader_version", "server_address", "server_port"];

function profileFromForm() {
  return {
    mc_version: $("profile-mc_version").value.trim(),
    loader: $("profile-loader").value,
    loader_version: $("profile-loader_version").value.trim() || null,
    server_address: $("profile-server_address").value.trim(),
    server_port: Number($("profile-server_port").value),
  };
}

function fillProfileForm() {
  const p = state.profile;
  $("profile-mc_version").value = p?.mc_version ?? "";
  $("profile-loader").value = p?.loader ?? "forge";
  $("profile-loader_version").value = p?.loader_version ?? "";
  $("profile-server_address").value = p?.server_address ?? "";
  $("profile-server_port").value = p?.server_port ?? 25565;
  onProfileInput();
}

function onProfileInput() {
  const isVanilla = $("profile-loader").value === "vanilla";
  $("field-loader-version").hidden = isVanilla;
  const form = profileFromForm();
  if (isVanilla) form.loader_version = null;
  const p = state.profile;
  const dirty = !p || PROFILE_FIELDS.some((k) => (form[k] ?? null) !== (p[k] ?? null));
  const complete = form.mc_version && form.server_address && form.server_port >= 1 && form.server_port <= 65535;
  $("profile-save").disabled = !dirty || !complete;
  $("profile-reset").hidden = !p || !dirty;
  $("profile-notice").hidden = !p || !dirty;
}

async function saveProfile(event) {
  event.preventDefault();
  const payload = profileFromForm();
  if ($("profile-loader").value === "vanilla") payload.loader_version = null;
  try {
    state.profile = await api("/admin/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderAll();
    toast("Профиль сохранён");
  } catch (err) {
    toast(err.message, true);
  }
}

// --- роутинг ---------------------------------------------------------------

function route() {
  const name = (location.hash.match(/^#\/(\w+)/) || [])[1];
  const page = ["overview", "mods", "server"].includes(name) ? name : "overview";
  for (const section of document.querySelectorAll(".page")) section.hidden = section.dataset.page !== page;
  for (const link of document.querySelectorAll("#nav a")) {
    if (link.dataset.route === page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

async function enterMain() {
  showScreen("main");
  route();
  try {
    await refreshAll();
  } catch (err) {
    toast(err.message, true);
  }
}

// --- инициализация ---------------------------------------------------------

function init() {
  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorEl = $("login-error");
    errorEl.hidden = true;
    try {
      const resp = await fetch("/api/v1/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: $("login-password").value }),
      });
      if (!resp.ok) throw new Error("Неверный пароль");
      setToken((await resp.json()).access_token);
      $("login-password").value = "";
      await enterMain();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });

  $("btn-logout").addEventListener("click", () => { clearToken(); showScreen("login"); });
  window.addEventListener("hashchange", route);

  // моды
  $("btn-add-mods").addEventListener("click", openAddDialog);
  $("mods-search").addEventListener("input", renderMods);
  $("mods-all-versions").addEventListener("change", renderMods);

  const dropzone = $("dropzone");
  const fileInput = $("file-input");
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
  fileInput.addEventListener("change", () => { addFiles(fileInput.files); fileInput.value = ""; });
  for (const ev of ["dragenter", "dragover"]) dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("over"); });
  for (const ev of ["dragleave", "drop"]) dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("over"); });
  dropzone.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));

  $("add-type-all").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-type]");
    if (!btn) return;
    bulkType = btn.dataset.type;
    for (const item of queue) if (item.status === "idle" || item.status === "err") item.type = bulkType;
    syncBulkType();
    renderQueue();
  });
  $("add-loader").addEventListener("input", updateSubmit);
  $("add-mc_version").addEventListener("input", updateSubmit);
  $("add-submit").addEventListener("click", submitUpload);

  // редактирование
  $("edit-form").addEventListener("input", syncEdit);
  $("edit-form").addEventListener("submit", saveEdit);
  $("edit-type").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-type]");
    if (!btn) return;
    editing.type = btn.dataset.type;
    syncEdit();
  });
  $("edit-cancel").addEventListener("click", () => $("dlg-edit").close());
  $("edit-close").addEventListener("click", () => $("dlg-edit").close());

  // профиль
  $("profile-form").addEventListener("input", onProfileInput);
  $("profile-form").addEventListener("submit", saveProfile);
  $("profile-reset").addEventListener("click", fillProfileForm);

  if (getToken()) enterMain();
  else showScreen("login");
}

init();
