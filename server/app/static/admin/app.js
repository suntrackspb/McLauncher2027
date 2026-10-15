const TOKEN_KEY = "mclauncher_admin_token";
const $ = (id) => document.getElementById(id);

const state = {
  profile: null, // null — профиль ещё не задан
  mods: [],
  authlib: [],
  launcher: null,
  connection: null,
  status: null, // ответ /admin/server/status, {error} или null
  // Сверка с сервером: null — не смотрели, {loading}, {plan, at} или {error}
  server: null,
  props: null, // {exists, values, can_control} | {error} | {loading}
};

const LOADERS = ["forge", "neoforge", "fabric", "quilt"];

// --- утилиты ---------------------------------------------------------------

function getToken() { return sessionStorage.getItem(TOKEN_KEY); }
function setToken(token) { sessionStorage.setItem(TOKEN_KEY, token); }
function clearToken() { sessionStorage.removeItem(TOKEN_KEY); }

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child != null && child !== false) node.append(child);
  }
  return node;
}

function toast(message, isError = false) {
  const node = el("div", { class: isError ? "toast err" : "toast", role: isError ? "alert" : null, text: message });
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

function timeShort(d) {
  return d.toLocaleTimeString("ru", { hour: "2-digit", minute: "2-digit" });
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

const jsonBody = (method, data) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

// Подтверждение в своём диалоге вместо confirm(): body — строка или узлы.
function confirmDialog({ title, body, ok, danger = false }) {
  const dlg = $("dlg-confirm");
  $("confirm-title").textContent = title;
  $("confirm-body").replaceChildren(...[body].flat().map((b) => typeof b === "string" ? el("p", { text: b }) : b));
  const btn = $("confirm-ok");
  btn.textContent = ok;
  btn.className = danger ? "btn btn-danger-solid" : "btn btn-primary";
  dlg.returnValue = "";
  dlg.showModal();
  btn.focus();
  return new Promise((resolve) => { dlg.onclose = () => resolve(dlg.returnValue === "ok"); });
}

function showScreen(name) {
  if (name === "login") stopTimers();
  $("screen-login").hidden = name !== "login";
  $("screen-main").hidden = name !== "main";
}

// --- загрузчики и версии -----------------------------------------------------

// data-loaders="vanilla" — добавить vanilla первым.
function fillLoaderSelects() {
  for (const select of document.querySelectorAll("select[data-loaders]")) {
    const values = select.dataset.loaders === "vanilla" ? ["vanilla", ...LOADERS] : LOADERS;
    select.replaceChildren(...values.map((v) => el("option", { value: v, text: v })));
  }
}

// Незнакомое значение (старые записи) добавляет отдельной опцией, а не теряет.
function setLoader(select, value) {
  const v = (value || "").toLowerCase();
  select.querySelector("option[data-extra]")?.remove();
  if (v && ![...select.options].some((o) => o.value === v)) {
    select.append(el("option", { value: v, text: `${v} (нет в списке)`, "data-extra": "" }));
  }
  select.value = v || select.options[0]?.value || "";
}

function fillVersionHints() {
  const versions = new Set(state.mods.map((m) => m.mc_version));
  if (state.profile) versions.add(state.profile.mc_version);
  const sorted = [...versions].sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
  $("mc-versions").replaceChildren(...sorted.map((v) => el("option", { value: v })));
}

function matchesProfile(mod) {
  const p = state.profile;
  return !!p && mod.loader.toLowerCase() === p.loader.toLowerCase() && mod.mc_version === p.mc_version;
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

async function loadMods() { state.mods = await api("/admin/mods"); }

async function loadExtras() {
  // публичные эндпоинты: падение одного не должно ломать остальную админку
  state.authlib = await api("/launcher/authlib-jars", {}, { auth: false }).catch(() => null);
  state.launcher = await api("/launcher/version", {}, { auth: false }).catch(() => null);
}

async function loadConnection() {
  state.connection = await api("/admin/server/connection").catch(() => null);
}

async function refreshAll() {
  const results = await Promise.allSettled([loadProfile(), loadMods(), loadExtras(), loadConnection()]);
  renderAll();
  fillConnForm();
  const failed = results.find((r) => r.status === "rejected");
  if (failed) toast(failed.reason.message, true);
}

function renderAll() {
  renderOverview();
  renderMods();
  renderStatusbar();
  fillVersionHints();
  if (!profileEdited) fillProfileForm();
  const forProfile = state.mods.filter(matchesProfile).length;
  $("nav-mods-badge").textContent = forProfile ? String(forProfile) : "";
  $("nav-settings-badge").textContent = !state.profile || !state.connection ? "!" : "";
}

// --- строка статуса ----------------------------------------------------------

const STATE_LABEL = {
  active: "Сервер работает", inactive: "Сервер остановлен", failed: "Сервер упал",
  activating: "Сервер запускается", deactivating: "Сервер останавливается", unknown: "Состояние неизвестно",
};
let statusTimer = null;
let statusBusy = false;

async function loadStatus() {
  if (!state.connection || statusBusy) return;
  statusBusy = true;
  try {
    state.status = await api("/admin/server/status");
  } catch (err) {
    state.status = { error: err.message };
  } finally {
    statusBusy = false;
  }
  renderStatusbar();
  renderConsoleAvailability();
}

// Лампа: active — горит, transition — мигает, off — тёмная, bad — красная.
function lampState(s) {
  if (!s || s.error) return s?.error ? "bad" : "off";
  const st = s.service_state;
  if (st === "active") return "active";
  if (st === "activating" || st === "deactivating") return "transition";
  if (st === "failed") return "bad";
  if (!st && s.players != null) return "active";
  return "off";
}

function playersLine(raw) {
  // «There are 2 of a max of 20 players online: Steve, Alex»
  const m = /(\d+)\D+?(\d+)[^:]*:\s*(.*)$/s.exec(raw || "");
  if (!m) return raw || "";
  const n = Number(m[1]);
  const names = m[3].trim();
  return n ? `${n} из ${m[2]} ${plural(Number(m[2]), "игрока", "игроков", "игроков")}: ${names}` : `Никого нет, мест: ${m[2]}`;
}

function renderStatusbar() {
  const p = state.profile;
  const s = state.status;
  const lamp = lampState(s);
  $("sb-lamp").className = `lamp ${lamp}`;
  const addr = p ? `${p.server_address}:${p.server_port}` : "";
  const build = p ? `${p.loader} ${p.mc_version}` : "";
  let title, sub;
  if (!state.connection) {
    title = "Сервер не подключён";
    sub = p ? `${build}, ${addr}` : "Задайте профиль и доступ в разделе «Подключение»";
  } else if (!s) {
    title = "Проверяю сервер…";
    sub = `${build}, ${addr}`;
  } else if (s.error) {
    title = "Нет связи с сервером";
    sub = s.error;
  } else {
    title = s.service_state ? (STATE_LABEL[s.service_state] || s.service_state) : (s.players != null ? STATE_LABEL.active : "Сервер подключён");
    const detail = s.players != null ? playersLine(s.players.replace(/§./g, "")) : (s.rcon_enabled ? s.rcon_error : "");
    sub = [build && `${build}, ${addr}`, detail].filter(Boolean).join(". ");
  }
  $("sb-state").textContent = title;
  $("sb-sub").textContent = sub;
  const canControl = !!s?.can_control;
  $("sb-actions").hidden = !canControl;
  if (canControl) {
    const st = s.service_state;
    $("sb-actions").querySelector("[data-action=start]").hidden = st === "active" || st === "activating";
    $("sb-actions").querySelector("[data-action=restart]").hidden = st !== "active";
    $("sb-actions").querySelector("[data-action=stop]").hidden = st !== "active" && st !== "activating";
  }
  $("sb-refresh").hidden = !state.connection;
}

function scheduleStatus(ms = 30000) {
  clearTimeout(statusTimer);
  statusTimer = setTimeout(async () => {
    if (!document.hidden) await loadStatus();
    scheduleStatus();
  }, ms);
}

// После старт/рестарт сервер ещё грузится — опрашиваем чаще ~30 с.
function pollStatusFast(left = 10) {
  clearTimeout(statusTimer);
  loadStatus().then(() => {
    if (left > 0) statusTimer = setTimeout(() => pollStatusFast(left - 1), 3000);
    else scheduleStatus();
  });
}

const ACTION_TEXT = {
  start: { ok: "Запустить", done: "Запускаю сервер" },
  restart: { ok: "Перезапустить", done: "Перезапускаю сервер", title: "Перезапустить сервер?" },
  stop: { ok: "Остановить", done: "Останавливаю сервер", title: "Остановить сервер?" },
};

async function serverAction(action) {
  const t = ACTION_TEXT[action];
  if (action !== "start") {
    const ok = await confirmDialog({ title: t.title, body: "Игроков на сервере отключит.", ok: t.ok, danger: action === "stop" });
    if (!ok) return;
  }
  const buttons = $("sb-actions").querySelectorAll("button");
  buttons.forEach((b) => { b.disabled = true; });
  $("sb-lamp").className = "lamp transition";
  $("sb-state").textContent = `${t.done}…`;
  try {
    await api(`/admin/server/control/${action}`, { method: "POST" });
    toast(`${t.done}`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    buttons.forEach((b) => { b.disabled = false; });
    pollStatusFast();
    setTimeout(loadLog, 1500);
  }
}

// --- обзор -----------------------------------------------------------------

function renderOverview() {
  const p = state.profile;
  const forProfile = state.mods.filter(matchesProfile);
  const required = forProfile.filter((m) => m.mod_type === "required");
  const checks = [];

  checks.push(p
    ? { level: "ok", title: "Профиль сервера задан", detail: `${p.loader} ${p.mc_version}, адрес ${p.server_address}:${p.server_port}`, link: ["#/settings", "Изменить"] }
    : { level: "bad", title: "Профиль сервера не задан", detail: "Без него лаунчер не знает, какую версию ставить и куда подключаться.", link: ["#/settings", "Задать"] });

  checks.push(state.connection
    ? { level: "ok", title: "Доступ к файлам сервера настроен", detail: `${state.connection.protocol.toUpperCase()} ${state.connection.host}, папка ${state.connection.server_dir}`, link: ["#/settings", "Изменить"] }
    : { level: "warn", title: "Доступ к файлам сервера не настроен", detail: "Без него админка не зальёт моды, не покажет лог и параметры игры.", link: ["#/settings", "Настроить"] });

  if (p) {
    if (p.loader === "vanilla") {
      checks.push({ level: "ok", title: "Моды не нужны", detail: "Профиль vanilla — лаунчер ставит игру без модов." });
    } else if (required.length) {
      checks.push({ level: "ok", title: `Обязательных модов: ${required.length}`, detail: `Необязательных: ${forProfile.length - required.length}`, link: ["#/mods", "Открыть"] });
    } else {
      const other = state.mods.length - forProfile.length;
      checks.push({
        level: "warn", title: "Для этого профиля нет обязательных модов",
        detail: other ? `Загружено модов для других версий: ${other}.` : "Игроки зайдут без модов.",
        link: ["#/mods", "Добавить"],
      });
    }
  }

  const plan = state.server?.plan;
  if (plan && planHasChanges(plan)) {
    checks.push({ level: "warn", title: "Сервер расходится с профилем", detail: planSummary(plan), link: ["#/mods", "Залить"] });
  }

  if (state.authlib === null) {
    checks.push({ level: "warn", title: "Не удалось получить список authlib", detail: "Запрос /launcher/authlib-jars завершился ошибкой." });
  } else if (state.authlib.length) {
    checks.push({ level: "ok", title: "Вход и скины через свой бэкенд", detail: `Версии authlib: ${state.authlib.map((j) => j.version).join(", ")}` });
  } else {
    checks.push({ level: "warn", title: "Нет пропатченных authlib", detail: "Положите authlib-<версия>_skinfix.jar в storage/authlib — без них игроки не войдут через этот бэкенд." });
  }

  if (state.launcher === null) {
    checks.push({ level: "warn", title: "Не удалось проверить релиз лаунчера", detail: "Бэкенд не достучался до GitHub." });
  } else if (state.launcher.version) {
    checks.push({ level: "ok", title: `Релиз лаунчера ${state.launcher.version}`, detail: "Лаунчеры со старой версией предложат обновиться." });
  } else {
    checks.push({ level: "warn", title: "Релиз лаунчера не найден", detail: "Проверьте LAUNCHER_GITHUB_REPO в .env и наличие релиза на GitHub." });
  }

  // Сначала проблемы.
  const order = { bad: 0, warn: 1, ok: 2 };
  checks.sort((a, b) => order[a.level] - order[b.level]);
  $("checks").replaceChildren(...checks.map((c) => el("li", { class: `check ${c.level}` },
    el("span", { class: "check-mark", "aria-hidden": "true" }),
    el("div", {}, el("div", { class: "check-title", text: c.title }), el("div", { class: "check-detail", text: c.detail })),
    c.link ? el("a", { class: "btn btn-sm", href: c.link[0], text: c.link[1] }) : null,
  )));
}

// --- моды: сверка с сервером ---------------------------------------------------

const AUTHLIB_STATE = {
  patched: ["ok", "уже наш"],
  to_patch: ["add", "заменю на наш"],
  no_patch: ["bad", "нет пропатченного authlib этой версии — игроки не войдут"],
};
let syncOpen = false;

function planHasChanges(r) {
  return !!(r.mods_upload.length || r.mods_remove.length || Object.values(r.authlib).includes("to_patch"));
}

function planSummary(r) {
  const patch = Object.values(r.authlib).filter((s) => s === "to_patch").length;
  return [
    r.mods_upload.length && `залить ${r.mods_upload.length} ${plural(r.mods_upload.length, "мод", "мода", "модов")}`,
    r.mods_remove.length && `убрать ${r.mods_remove.length} лишних`,
    patch && "заменить authlib",
  ].filter(Boolean).join(", ");
}

async function checkServer() {
  if (!state.connection || state.server?.loading) return;
  state.server = { loading: true };
  renderMods();
  try {
    state.server = { plan: await api("/admin/server/sync"), at: new Date() };
  } catch (err) {
    state.server = { error: err.message };
  }
  renderMods();
  renderOverview();
}

// Набор модов поменялся — сверка устарела.
function staleServer() {
  if (state.server?.plan) checkServer();
}

async function applySync() {
  const plan = state.server?.plan;
  if (!plan) return;
  const ok = await confirmDialog({
    title: "Залить на сервер?",
    body: [
      el("p", { text: `Сделаю: ${planSummary(plan)}.` }),
      el("p", { class: "muted small", text: "Лишние моды не удаляются, а переезжают в mods_removed/. Оригинальный authlib остаётся рядом как .orig." }),
    ],
    ok: "Залить",
  });
  if (!ok) return;
  state.server = { ...state.server, applying: true };
  renderMods();
  try {
    const r = await api("/admin/server/sync", jsonBody("POST", { plan_id: plan.plan_id }));
    // После заливки сервер совпадает с профилем — перечитывать не нужно.
    state.server = {
      plan: { ...r, mods_ok: [...r.mods_ok, ...r.mods_upload].sort(), mods_upload: [], mods_remove: [],
        authlib: Object.fromEntries(Object.entries(r.authlib).map(([v, s]) => [v, s === "to_patch" ? "patched" : s])) },
      at: new Date(), applied: r,
    };
    syncOpen = true;
  } catch (err) {
    if (err.status === 409) {
      toast("На сервере что-то поменялось с момента проверки — сверяю заново", true);
      state.server = null;
      await checkServer();
      return;
    }
    state.server = { ...state.server, applying: false };
    toast(err.message, true);
  }
  renderMods();
  renderOverview();
}

function renderSync() {
  const s = state.server;
  const box = $("sync");
  const text = $("sync-text");
  const actions = $("sync-actions");
  const body = $("sync-body");
  box.className = "sync";
  actions.replaceChildren();
  body.hidden = true;

  if (!state.connection) {
    box.classList.add("idle");
    text.replaceChildren(el("strong", { text: "Сервер не подключён" }), el("span", { text: "Без доступа к файлам не видно, какие моды лежат в mods/ сервера." }));
    actions.append(el("a", { class: "btn btn-sm", href: "#/settings", text: "Настроить доступ" }));
    return;
  }
  if (!s) {
    box.classList.add("idle");
    text.replaceChildren(el("strong", { text: "Сервер не сверялся" }), el("span", { text: "Проверю, какие моды и authlib лежат на сервере." }));
    actions.append(el("button", { class: "btn btn-sm btn-primary", type: "button", text: "Сверить с сервером", onclick: checkServer }));
    return;
  }
  if (s.loading) {
    box.classList.add("idle");
    text.replaceChildren(el("strong", { text: "Сверяю с сервером…" }), el("span", { text: "Читаю mods/ и libraries/." }));
    return;
  }
  if (s.error) {
    box.classList.add("bad");
    text.replaceChildren(el("strong", { text: "Не удалось прочитать сервер" }), el("span", { text: s.error }));
    actions.append(el("button", { class: "btn btn-sm", type: "button", text: "Повторить", onclick: checkServer }));
    return;
  }

  const r = s.plan;
  const changes = planHasChanges(r);
  const noAuthlib = !Object.keys(r.authlib).length || Object.values(r.authlib).includes("no_patch");
  const onServer = r.mods_ok.length + r.mods_remove.length;

  if (s.applied) {
    box.classList.add("ok");
    text.replaceChildren(el("strong", { text: "Залито на сервер" }), el("span", { text: "Изменения вступят в силу после перезапуска сервера." }));
    if (state.status?.can_control) actions.append(el("button", { class: "btn btn-sm btn-primary", type: "button", text: "Перезапустить", onclick: () => serverAction("restart") }));
  } else if (changes) {
    box.classList.add("warn");
    text.replaceChildren(el("strong", { text: "Сервер расходится с профилем" }), el("span", { text: `Нужно ${planSummary(r)}.` }));
  } else {
    box.classList.add(noAuthlib ? "bad" : "ok");
    text.replaceChildren(
      el("strong", { text: noAuthlib ? "Моды совпадают, но authlib не готов" : "Сервер совпадает с профилем" }),
      el("span", { text: `На сервере ${onServer} ${plural(onServer, "мод", "мода", "модов")}. Сверено в ${timeShort(s.at)}.` }));
  }

  actions.append(
    el("button", { class: "btn btn-sm btn-ghost", type: "button", "aria-expanded": String(syncOpen), text: syncOpen ? "Скрыть детали" : "Детали", onclick: () => { syncOpen = !syncOpen; renderSync(); } }),
    el("button", { class: "btn btn-sm btn-ghost", type: "button", text: "Сверить заново", disabled: s.applying, onclick: () => { state.server = null; checkServer(); } }),
  );
  if (changes && !s.applied) {
    actions.append(el("button", { class: "btn btn-sm btn-primary", type: "button", disabled: s.applying, text: s.applying ? "Заливаю…" : "Залить на сервер", onclick: applySync }));
  }

  if (!syncOpen) return;
  body.hidden = false;
  const rows = [
    ...r.mods_upload.map((n) => ["add", "залить", n]),
    ...r.mods_remove.map((n) => ["del", "в mods_removed/", n]),
    ...r.mods_ok.map((n) => ["same", "на месте", n]),
  ];
  const authlib = Object.entries(r.authlib);
  body.replaceChildren(
    el("h3", { text: "mods/" }),
    rows.length
      ? el("ul", { class: "diff" }, rows.map(([cls, what, name]) => el("li", { class: cls }, el("span", { class: "diff-op", text: what }), el("span", { class: "mono", text: name }))))
      : el("p", { class: "muted small", text: "Серверных модов в профиле нет." }),
    el("h3", { text: "authlib" }),
    authlib.length
      ? el("ul", { class: "diff" }, authlib.map(([v, st]) => el("li", { class: AUTHLIB_STATE[st][0] }, el("span", { class: "diff-op", text: AUTHLIB_STATE[st][1] }), el("span", { class: "mono", text: v }))))
      : el("p", { class: "small bad-text", text: "authlib не найден в libraries/ — сервер ещё не запускался или устроен иначе (vanilla распаковывает библиотеки при старте)." }),
    s.applied?.backup_dir ? el("p", { class: "muted small mono", text: `Бэкап: ${s.applied.backup_dir}` }) : null,
  );
}

function serverModState(mod) {
  const plan = state.server?.plan;
  if (!plan || !matchesProfile(mod) || mod.server_side === false) return null;
  if (plan.mods_ok.includes(mod.file_name)) return "ok";
  if (plan.mods_upload.includes(mod.file_name)) return "missing";
  return null; // добавлен после проверки
}

// --- моды: список --------------------------------------------------------------

let modsFilter = "all";

function renderMods() {
  renderSync();
  const p = state.profile;
  $("mods-lead").textContent = p
    ? (p.loader === "vanilla" ? "Профиль vanilla — лаунчер ставит игру без модов." : `Под профиль ${p.loader} ${p.mc_version}. Лаунчер скачивает их игрокам, серверные — заливаются на сервер.`)
    : "Сначала задайте профиль сервера в разделе «Подключение».";

  const root = $("mods-list");
  const query = $("mods-search").value.trim().toLowerCase();
  const showAll = $("mods-all-versions").checked;
  const visible = state.mods.filter((m) =>
    (showAll || matchesProfile(m)) &&
    (modsFilter === "all" || m.mod_type === modsFilter) &&
    (!query || m.name.toLowerCase().includes(query) || m.file_name.toLowerCase().includes(query)));

  const stray = (!query && state.server?.plan?.mods_remove) || [];
  const strayBlock = stray.length ? [
    el("div", { class: "group-title" }, el("h2", { text: "Есть только на сервере" }), el("span", { class: "count", text: String(stray.length) })),
    el("p", { class: "group-hint", text: "Лежат в mods/ сервера, но в профиле не отмечены как серверные. При заливке переедут в mods_removed/. Нужный — загрузите сюда." }),
    el("ul", { class: "stray-list" }, stray.map((name) => el("li", { class: "mono", text: name }))),
  ] : [];

  if (!visible.length) {
    const hiddenOther = !showAll && state.mods.length && !query;
    root.replaceChildren(el("div", { class: "empty" },
      el("p", { class: "empty-title", text: query ? `Среди загруженных нет «${$("mods-search").value.trim()}»` : hiddenOther ? "Для текущего профиля модов нет" : "Модов пока нет" }),
      el("p", { text: query ? "Поищите его на Modrinth — добавлю вместе с зависимостями." : hiddenOther ? `Загружено для других версий: ${state.mods.length}. Включите «Другие версии», чтобы их увидеть.` : "Загрузите jar или найдите мод на Modrinth." }),
      el("div", { class: "empty-actions" },
        el("button", { class: "btn btn-primary", type: "button", text: query ? "Искать на Modrinth" : "Найти на Modrinth", onclick: openModrinth }),
        query ? null : el("button", { class: "btn", type: "button", text: "Загрузить jar", onclick: openAddDialog })),
    ), ...strayBlock);
    return;
  }

  const groups = [
    ["required", "Обязательные", "Скачиваются всем игрокам. Лишние моды у игрока удаляются."],
    ["optional", "Необязательные", "Игрок сам включает их в лаунчере."],
  ];
  const blocks = [];
  for (const [type, title, hint] of groups) {
    const items = visible.filter((m) => m.mod_type === type);
    if (!items.length) continue;
    blocks.push(
      el("div", { class: "group-title" }, el("h2", { text: title }), el("span", { class: "count", text: String(items.length) })),
      el("p", { class: "group-hint", text: hint }),
      el("ul", { class: "mods" }, items.map(modRow)),
    );
  }
  root.replaceChildren(...blocks, ...strayBlock);
}

function modRow(mod) {
  const other = !matchesProfile(mod);
  const srv = serverModState(mod);
  const where = mod.server_side === false
    ? el("span", { class: "tag", text: "только у игроков" })
    : srv === "ok" ? el("span", { class: "tag tag-ok", text: "на сервере" })
    : srv === "missing" ? el("span", { class: "tag tag-warn", text: "не залит" })
    : null;
  return el("li", { class: other ? "mod other" : "mod" },
    el("div", { class: "mod-main" },
      el("div", { class: "mod-name" }, el("span", { text: mod.name }), other ? el("span", { class: "tag tag-warn", text: `${mod.loader} ${mod.mc_version}` }) : null, where),
      mod.description ? el("div", { class: "mod-desc", text: mod.description }) : null,
      el("div", { class: "mod-file mono", text: `${mod.file_name}, ${formatSize(mod.size)}` }),
    ),
    el("div", { class: "mod-actions" },
      el("button", { class: "btn btn-sm btn-ghost", type: "button", text: "Изменить", onclick: () => openEdit(mod) }),
      el("button", { class: "btn btn-sm btn-ghost btn-ghost-danger", type: "button", text: "Удалить", onclick: () => askDelete(mod) }),
    ),
  );
}

// --- Modrinth ---------------------------------------------------------------

let mrType = "required";

function openModrinth() {
  const p = state.profile;
  $("mr-profile").textContent = p
    ? `Ищу версии под ${p.loader} ${p.mc_version}.`
    : "Сначала задайте профиль сервера — моды ищутся под его загрузчик и версию.";
  $("mr-results").replaceChildren();
  const query = $("mods-search").value.trim();
  if (query) $("mr-query").value = query;
  $("dlg-modrinth").showModal();
  $("mr-query").focus();
  if (query) $("mr-form").requestSubmit();
}

function syncMrType() {
  for (const b of $("mr-type").querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.type === mrType));
}

function formatDownloads(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} млн`;
  if (n >= 1e3) return `${Math.round(n / 1e3)} тыс.`;
  return String(n);
}

const SIDE_LABEL = { required: "нужен", optional: "по желанию", unsupported: "не нужен" };

async function searchModrinth(event) {
  event.preventDefault();
  const root = $("mr-results");
  root.replaceChildren(el("li", { class: "muted", text: "Ищу…" }));
  try {
    const hits = await api(`/admin/modrinth/search?q=${encodeURIComponent($("mr-query").value.trim())}`);
    root.replaceChildren(...(hits.length ? hits.map(modrinthRow) : [el("li", { class: "muted", text: "Под этот профиль ничего не нашлось" })]));
  } catch (err) {
    root.replaceChildren(el("li", { class: "error-text", text: err.message }));
  }
}

function modrinthRow(hit) {
  const installedIds = new Set(state.mods.filter(matchesProfile).map((m) => m.modrinth_project_id).filter(Boolean));
  const already = installedIds.has(hit.project_id);
  const btn = el("button", { class: "btn btn-sm btn-primary", type: "button", text: already ? "Уже добавлен" : "Добавить", disabled: already });
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.textContent = "Скачиваю…";
    try {
      const res = await api("/admin/modrinth/install", jsonBody("POST", { project_id: hit.project_id, mod_type: mrType }));
      const names = res.installed.map((m) => m.name);
      btn.textContent = "Добавлен";
      toast(names.length ? `Добавлено: ${names.join(", ")}` : `Уже есть: ${res.skipped.join(", ")}`);
      await loadMods();
      renderAll();
      staleServer();
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "Добавить";
      toast(err.message, true);
    }
  });
  return el("li", {},
    hit.icon_url ? el("img", { src: hit.icon_url, alt: "", loading: "lazy" }) : el("div", { class: "mr-noicon" }),
    el("div", {}, el("div", { class: "mr-title", text: hit.title }),
      el("div", { class: "mr-meta", text: `${formatDownloads(hit.downloads)} загрузок. Клиент: ${SIDE_LABEL[hit.client_side] || "?"}, сервер: ${SIDE_LABEL[hit.server_side] || "?"}` })),
    btn,
    hit.description ? el("div", { class: "mr-desc", text: hit.description }) : null,
  );
}

// --- удаление и редактирование мода ---------------------------------------------

async function askDelete(mod) {
  const ok = await confirmDialog({
    title: `Удалить «${mod.name}»?`,
    body: [el("p", { class: "mono small", text: mod.file_name }), "Мод пропадёт из списка, файл удалится. Игроки перестанут получать его при следующем запуске лаунчера."],
    ok: "Удалить", danger: true,
  });
  if (!ok) return;
  try {
    await api(`/admin/mods/${mod.id}`, { method: "DELETE" });
    toast(`Удалён: ${mod.name}`);
    await loadMods();
    renderAll();
    staleServer();
  } catch (err) {
    toast(err.message, true);
  }
}

let editing = null; // {mod, type}

function editValues() {
  return {
    name: $("edit-name").value.trim(),
    description: $("edit-description").value.trim() || null,
    mod_type: editing.type,
    loader: $("edit-loader").value,
    mc_version: $("edit-mc_version").value.trim(),
    server_side: $("edit-server_side").checked,
  };
}

function editChanges() {
  const values = editValues();
  // Исходные значения приводим к виду формы, иначе "" vs null дают «изменения» без правок.
  const orig = { ...editing.mod, description: editing.mod.description || null, server_side: editing.mod.server_side !== false };
  const changes = {};
  for (const key of Object.keys(values)) {
    const was = key === "loader" ? orig.loader.toLowerCase() : (orig[key] ?? null);
    if (values[key] !== was) changes[key] = values[key];
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
  setLoader($("edit-loader"), mod.loader);
  $("edit-mc_version").value = mod.mc_version;
  $("edit-server_side").checked = mod.server_side !== false;
  syncEdit();
  $("dlg-edit").showModal();
}

async function saveEdit(event) {
  event.preventDefault();
  const changes = editChanges();
  if (!Object.keys(changes).length) return;
  $("edit-save").disabled = true;
  try {
    await api(`/admin/mods/${editing.mod.id}`, jsonBody("PATCH", changes));
    $("dlg-edit").close();
    toast(`Сохранено: ${changes.name ?? editing.mod.name}`);
    await loadMods();
    renderAll();
    staleServer();
  } catch (err) {
    toast(err.message, true);
    syncEdit();
  }
}

// --- загрузка jar ------------------------------------------------------------

let queue = []; // {file, name, description, type, status: "idle"|"busy"|"ok"|"err", error}
let bulkType = "required";

function guessName(fileName) {
  let base = fileName.replace(/\.jar$/i, "");
  base = base.replace(/[-_+ ](?:v|mc)?\d.*$/i, "") || base;
  base = base.replace(/[-_]+/g, " ").trim();
  return base ? base[0].toUpperCase() + base.slice(1) : fileName;
}

function openAddDialog() {
  queue = [];
  bulkType = "required";
  setLoader($("add-loader"), state.profile?.loader !== "vanilla" ? state.profile?.loader : "");
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
  const wrap = el("div", { class: "segmented segmented-sm", role: "group", "aria-label": "Тип мода" });
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
      type: "text", value: item.name, "aria-label": `Название для ${item.file.name}`, disabled: locked,
      oninput: (e) => { item.name = e.target.value; updateSubmit(); },
    });
    const descInput = el("input", {
      type: "text", value: item.description, placeholder: "Описание, необязательно", "aria-label": `Описание для ${item.file.name}`, disabled: locked,
      oninput: (e) => { item.description = e.target.value; },
    });
    const li = el("li", {},
      nameInput,
      locked ? el("span") : typeToggle(item),
      locked ? el("span") : el("button", {
        class: "btn btn-ghost btn-sm", type: "button", text: "Убрать",
        onclick: () => { queue.splice(queue.indexOf(item), 1); renderQueue(); },
      }),
      el("div", { class: "q-desc" }, descInput),
      el("div", { class: "q-file", text: `${item.file.name}, ${formatSize(item.file.size)}` }),
    );
    if (item.status === "busy") li.append(el("div", { class: "q-state", text: "Загружаю…" }));
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
  $("add-submit").textContent = todo.length > 1 ? `Загрузить ${todo.length}` : "Загрузить";
  $("add-summary").textContent = queue.length
    ? `${queue.length} ${plural(queue.length, "файл", "файла", "файлов")} для ${$("add-loader").value || "?"} ${$("add-mc_version").value || "?"}`
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
  if (done) staleServer();
  if (!failed) {
    $("dlg-add").close();
    toast(`Загружено: ${done}`);
  } else {
    toast(`Загружено: ${done}, с ошибкой: ${failed}`, true);
  }
}

// --- консоль -----------------------------------------------------------------

let logTimer = null;
let logBusy = false;

function renderConsoleAvailability() {
  const s = state.status;
  const ready = s && !s.error;
  $("rcon-form").hidden = !(ready && s.rcon_enabled);
  $("rcon-off").hidden = !(ready && !s.rcon_enabled);
}

async function enterConsole() {
  if (!state.connection) {
    $("console-hint").textContent = "Сначала настройте доступ к серверу в разделе «Подключение».";
    $("log-output").textContent = "";
    return;
  }
  $("console-hint").textContent = "Лог сервера и команды через RCON.";
  renderConsoleAvailability();
  await loadLog();
  syncLogFollow();
}

function leaveConsole() {
  clearTimeout(logTimer);
  logTimer = null;
}

function stopTimers() {
  leaveConsole();
  clearTimeout(statusTimer);
  statusTimer = null;
}

async function loadLog() {
  if (logBusy || !state.connection) return;
  logBusy = true;
  const out = $("log-output");
  try {
    const r = await api("/admin/server/log?lines=400");
    const atBottom = out.scrollHeight - out.scrollTop - out.clientHeight < 40;
    out.textContent = r.missing ? "logs/latest.log пока нет — сервер ещё не запускался." : r.lines.join("\n");
    if (atBottom || !out.dataset.loaded) out.scrollTop = out.scrollHeight;
    out.dataset.loaded = "1";
  } catch (err) {
    out.textContent = err.message;
  } finally {
    logBusy = false;
  }
}

// Следующий запрос — только после ответа предыдущего (SFTP/FTP бывает медленным).
function syncLogFollow() {
  clearTimeout(logTimer);
  logTimer = null;
  if (!$("log-follow").checked || currentPage !== "console") return;
  const tick = async () => {
    if (!document.hidden) await loadLog();
    if ($("log-follow").checked && logTimer !== null) logTimer = setTimeout(tick, 3000);
  };
  logTimer = setTimeout(tick, 3000);
}

async function sendRcon(event) {
  event.preventDefault();
  const input = $("rcon-input");
  const cmd = input.value.trim().replace(/^\//, "");
  if (!cmd) return;
  const out = $("rcon-output");
  out.hidden = false;
  const append = (text, cls) => {
    out.append(el("span", { class: cls, text: text + "\n" }));
    out.scrollTop = out.scrollHeight;
  };
  append(`> ${cmd}`, "cmd");
  input.value = "";
  try {
    const r = await api("/admin/server/rcon", jsonBody("POST", { command: cmd }));
    // Minecraft красит ответы §-кодами — в браузере они лишние.
    append(r.output.replace(/§./g, "") || "(пустой ответ)");
  } catch (err) {
    append(err.message, "err");
  }
}

async function enableRcon() {
  const btn = $("rcon-enable");
  btn.disabled = true;
  try {
    const r = await api("/admin/server/rcon/enable", { method: "POST" });
    state.props = null;
    if (r.restarted) {
      toast("RCON включён, сервер перезапускается — команды заработают после загрузки мира");
      pollStatusFast(20);
    } else if (r.needs_restart) {
      toast("RCON включён в server.properties. Перезапустите сервер через панель хостера.");
      await loadStatus();
    } else {
      toast("RCON включён — заработает при следующем запуске сервера");
      await loadStatus();
    }
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
  }
}

// --- параметры игры (server.properties) -------------------------------------------

let propEdits = {}; // key → новое значение

async function loadProps() {
  if (!state.connection) {
    state.props = { error: "Сначала настройте доступ к серверу в разделе «Подключение»." };
    renderProps();
    return;
  }
  state.props = { loading: true };
  renderProps();
  try {
    state.props = await api("/admin/server/properties");
  } catch (err) {
    state.props = { error: err.message };
  }
  propEdits = {};
  renderProps();
}

function propsVersion() {
  return parseMcVersion(state.profile?.mc_version);
}

// Видимые параметры: из схемы под версию профиля + всё, что реально есть в файле.
function visibleProps() {
  const values = state.props?.values || {};
  const version = propsVersion();
  const known = new Map();
  for (const prop of PROP_SCHEMA) {
    if (propAppliesTo(prop, version)) known.set(prop.key, prop);
  }
  // Ключ есть в файле, но для этой версии не в схеме — берём любое описание, иначе «Прочее».
  for (const key of Object.keys(values)) {
    if (known.has(key)) continue;
    const any = PROP_SCHEMA.find((p) => p.key === key);
    known.set(key, any ? { ...any, since: undefined, until: undefined } : { key, group: "other", type: guessType(values[key]), def: "", label: key, custom: true });
  }
  for (const key of Object.keys(propEdits)) {
    if (!known.has(key)) known.set(key, { key, group: "other", type: "text", def: "", label: key, custom: true });
  }
  return [...known.values()];
}

function guessType(v) {
  return v === "true" || v === "false" ? "bool" : "text";
}

function propCurrent(prop) {
  const values = state.props?.values || {};
  return prop.key in values ? values[prop.key] : prop.def;
}

function propValue(prop) {
  return prop.key in propEdits ? propEdits[prop.key] : propCurrent(prop);
}

function setPropEdit(prop, value) {
  if (value === propCurrent(prop)) delete propEdits[prop.key];
  else propEdits[prop.key] = value;
  const row = document.querySelector(`.prop[data-key="${CSS.escape(prop.key)}"]`);
  row?.classList.toggle("dirty", prop.key in propEdits);
  renderSavebar();
}

function propControl(prop) {
  const value = propValue(prop);
  const id = `prop-${prop.key}`;
  if (prop.type === "bool") {
    const input = el("input", { type: "checkbox", id, role: "switch", class: "toggle" });
    input.checked = value === "true";
    input.addEventListener("change", () => setPropEdit(prop, String(input.checked)));
    return input;
  }
  if (prop.type === "enum") {
    const options = [...prop.options];
    if (value && !options.some(([v]) => v === value)) options.push([value, value]);
    const select = el("select", { id }, options.map(([v, label]) => el("option", { value: v, text: label })));
    select.value = value;
    select.addEventListener("change", () => setPropEdit(prop, select.value));
    return select;
  }
  const input = el("input", {
    id, class: prop.mono === false ? null : "mono",
    type: prop.type === "int" ? "number" : prop.type === "secret" ? "password" : "text",
    min: prop.min, max: prop.max, step: prop.type === "int" ? 1 : null,
    placeholder: prop.def || "пусто",
    list: prop.suggest ? `${id}-list` : null,
    autocomplete: "off", spellcheck: "false",
  });
  input.value = value;
  input.addEventListener("input", () => setPropEdit(prop, input.value));
  if (!prop.suggest && prop.type !== "secret") return input;
  const wrap = el("div", { class: "prop-input-wrap" }, input);
  if (prop.suggest) wrap.append(el("datalist", { id: `${id}-list` }, prop.suggest.map((v) => el("option", { value: v }))));
  if (prop.type === "secret") {
    wrap.append(el("button", { type: "button", class: "btn btn-sm btn-ghost", text: "Показать", onclick: (e) => {
      const shown = input.type === "text";
      input.type = shown ? "password" : "text";
      e.target.textContent = shown ? "Показать" : "Скрыть";
    } }));
  }
  return wrap;
}

function renderProps() {
  const root = $("props-root");
  const p = state.props;
  const v = state.profile?.mc_version;
  $("props-lead").textContent = v && propsVersion()
    ? `server.properties на сервере. Показаны параметры Minecraft ${v} и всё, что уже записано в файле, включая параметры модов.`
    : "server.properties на сервере. Версия профиля неизвестна — показаны параметры актуального Minecraft и всё, что есть в файле.";
  $("props-search").hidden = !p?.values;

  if (!p || p.loading) {
    root.replaceChildren(el("p", { class: "muted", text: "Читаю server.properties…" }));
    renderSavebar();
    return;
  }
  if (p.error) {
    root.replaceChildren(el("div", { class: "empty" },
      el("p", { class: "empty-title", text: "Параметры недоступны" }),
      el("p", { text: p.error }),
      state.connection
        ? el("button", { class: "btn", type: "button", text: "Повторить", onclick: loadProps })
        : el("a", { class: "btn btn-primary", href: "#/settings", text: "Настроить доступ" })));
    renderSavebar();
    return;
  }

  const query = $("props-search").value.trim().toLowerCase();
  const props = visibleProps().filter((prop) => !query
    || prop.key.toLowerCase().includes(query) || prop.label.toLowerCase().includes(query) || (prop.desc || "").toLowerCase().includes(query));

  const blocks = [];
  if (!p.exists) {
    blocks.push(el("p", { class: "notice", text: "На сервере нет server.properties — он появится после первого запуска. Можно задать значения заранее: файл будет создан при сохранении." }));
  }
  for (const [group, title] of PROP_GROUPS) {
    const items = props.filter((prop) => prop.group === group);
    if (!items.length && !(group === "other" && !query)) continue;
    blocks.push(el("section", { class: "prop-group" },
      el("h2", { text: title }),
      group === "other" ? el("p", { class: "group-hint", text: "Параметры из файла, которых нет в ванильном Minecraft этой версии: их добавляют моды, ядра или старые версии." }) : null,
      el("ul", { class: "props" }, items.map(propRow)),
      group === "other" && !query ? addPropForm() : null,
    ));
  }
  if (!blocks.length) blocks.push(el("p", { class: "muted", text: `Нет параметров по запросу «${$("props-search").value.trim()}».` }));
  root.replaceChildren(...blocks);
  renderSavebar();
}

function propRow(prop) {
  const values = state.props?.values || {};
  const inFile = prop.key in values;
  return el("li", { class: `prop${prop.key in propEdits ? " dirty" : ""}${prop.type === "bool" ? " prop-bool" : ""}`, "data-key": prop.key },
    el("div", { class: "prop-label" },
      el("label", { for: `prop-${prop.key}`, text: prop.label }),
      el("div", { class: "prop-key mono" }, prop.custom ? null : prop.key, !inFile && !prop.custom ? el("span", { class: "prop-absent", text: "нет в файле, по умолчанию" }) : null),
      prop.desc ? el("p", { class: "prop-desc", text: prop.desc }) : null,
    ),
    el("div", { class: "prop-control" }, propControl(prop)),
  );
}

function addPropForm() {
  const key = el("input", { type: "text", class: "mono", placeholder: "имя-параметра", "aria-label": "Имя параметра", autocomplete: "off", spellcheck: "false" });
  const value = el("input", { type: "text", class: "mono", placeholder: "значение", "aria-label": "Значение", autocomplete: "off", spellcheck: "false" });
  return el("form", { class: "prop-add", onsubmit: (e) => {
    e.preventDefault();
    const k = key.value.trim();
    if (!/^[A-Za-z0-9._-]{1,128}$/.test(k)) {
      toast("Имя параметра: латиница, цифры, точка, дефис и подчёркивание", true);
      return;
    }
    propEdits[k] = value.value;
    renderProps();
    document.getElementById(`prop-${k}`)?.focus();
  } },
  key, value, el("button", { class: "btn btn-sm", type: "submit", text: "Добавить параметр" }));
}

function renderSavebar() {
  const n = Object.keys(propEdits).length;
  $("props-savebar").hidden = !n;
  $("props-dirty").textContent = `Изменено: ${n}`;
  $("props-save-restart").hidden = !(state.props?.can_control && state.status?.service_state === "active");
}

async function saveProps(restart) {
  const updates = { ...propEdits };
  for (const prop of visibleProps()) {
    if (prop.type === "int" && prop.key in updates && updates[prop.key] !== "" && !/^-?\d+$/.test(updates[prop.key])) {
      toast(`${prop.label}: нужно целое число`, true);
      document.getElementById(`prop-${prop.key}`)?.focus();
      return;
    }
  }
  for (const id of ["props-save", "props-save-restart"]) $(id).disabled = true;
  try {
    state.props = await api("/admin/server/properties", jsonBody("PUT", { updates }));
    propEdits = {};
    renderProps();
    if (restart) {
      await api("/admin/server/control/restart", { method: "POST" });
      toast("Сохранено, сервер перезапускается");
      pollStatusFast();
    } else {
      toast("Сохранено. Сервер прочитает параметры при следующем запуске.");
    }
    if ("enable-rcon" in updates || "rcon.password" in updates || "rcon.port" in updates) loadStatus();
  } catch (err) {
    toast(err.message, true);
  } finally {
    for (const id of ["props-save", "props-save-restart"]) $(id).disabled = false;
  }
}

// --- подключение: профиль -----------------------------------------------------

const PROFILE_FIELDS = ["mc_version", "loader", "loader_version", "server_address", "server_port"];
let profileEdited = false;

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
  profileEdited = false;
  const p = state.profile;
  $("profile-mc_version").value = p?.mc_version ?? "";
  setLoader($("profile-loader"), p?.loader ?? "forge");
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
  const complete = form.mc_version && form.server_address && Number.isInteger(form.server_port) && form.server_port >= 1 && form.server_port <= 65535;
  $("profile-save").disabled = !dirty || !complete;
  $("profile-reset").hidden = !p || !dirty;
  $("profile-notice").hidden = !p || !dirty;
}

async function saveProfile(event) {
  event.preventDefault();
  const payload = profileFromForm();
  if ($("profile-loader").value === "vanilla") payload.loader_version = null;
  try {
    state.profile = await api("/admin/profile", jsonBody("PUT", payload));
    profileEdited = false;
    state.server = null;
    renderAll();
    toast("Профиль сохранён");
  } catch (err) {
    toast(err.message, true);
  }
}

// --- подключение: доступ к файлам -----------------------------------------------

const DEFAULT_PORTS = { sftp: 22, ftp: 21, ftps: 21 };

function showHostKey() {
  const c = state.connection;
  $("conn-hostkey").hidden = !c?.host_key;
  $("conn-hostkey").textContent = c?.host_key ? `Ключ хоста: ${c.host_key.slice(0, 60)}…` : "";
  $("conn-reset-key").hidden = !c?.host_key;
}

function fillConnForm() {
  const c = state.connection;
  $("conn-protocol").value = c?.protocol ?? "sftp";
  $("conn-host").value = c?.host ?? "";
  $("conn-port").value = c?.port ?? "";
  $("conn-username").value = c?.username ?? "";
  $("conn-server_dir").value = c?.server_dir ?? "";
  $("conn-service_name").value = c?.service_name ?? "";
  $("conn-password").value = "";
  $("conn-key").value = "";
  const saved = [c?.has_password && "пароль", c?.has_private_key && "SSH-ключ"].filter(Boolean);
  $("conn-secrets-hint").hidden = !saved.length;
  $("conn-secrets-hint").textContent = saved.length ? `Сохранён ${saved.join(" и ")}. Оставьте поле пустым, чтобы не менять.` : "";
  showHostKey();
  $("conn-test").disabled = !c;
  onConnProtocol();
}

function onConnProtocol() {
  const proto = $("conn-protocol").value;
  $("field-conn-key").hidden = proto !== "sftp";
  $("field-conn-service").hidden = proto !== "sftp";
  $("conn-port").placeholder = String(DEFAULT_PORTS[proto]);
}

async function saveConnection(event, { resetHostKey = false } = {}) {
  event?.preventDefault();
  const proto = $("conn-protocol").value;
  const body = {
    protocol: proto,
    host: $("conn-host").value.trim(),
    port: Number($("conn-port").value) || null,
    username: $("conn-username").value.trim(),
    server_dir: $("conn-server_dir").value.trim(),
    service_name: proto === "sftp" ? ($("conn-service_name").value.trim() || null) : null,
    // пустое поле = не менять сохранённое
    password: $("conn-password").value || null,
    private_key: proto === "sftp" ? ($("conn-key").value.trim() || null) : null,
    reset_host_key: resetHostKey,
  };
  if (!body.host || !body.username || !body.server_dir) {
    toast("Заполните хост, пользователя и папку сервера", true);
    return;
  }
  try {
    state.connection = await api("/admin/server/connection", jsonBody("PUT", body));
    fillConnForm();
    state.server = null;
    state.props = null;
    state.status = null;
    renderAll();
    loadStatus();
    toast("Доступ сохранён");
  } catch (err) {
    toast(err.message, true);
  }
}

async function testConnection() {
  const btn = $("conn-test");
  btn.disabled = true;
  btn.textContent = "Подключаюсь…";
  try {
    const r = await api("/admin/server/connection/test", { method: "POST" });
    const missing = [!r.mods_dir && "mods/", !r.libraries_dir && "libraries/", !r.server_properties && "server.properties"].filter(Boolean);
    toast(missing.length ? `Подключился, но в папке нет: ${missing.join(", ")}` : "Подключение работает", !!missing.length);
    // Обновляем только ключ хоста — несохранённые правки формы не трогаем.
    await loadConnection();
    showHostKey();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.textContent = "Проверить подключение";
    btn.disabled = !state.connection;
  }
}

// --- роутинг ---------------------------------------------------------------

const PAGES = ["overview", "mods", "console", "properties", "settings"];
let currentPage = null;

async function route() {
  const name = (location.hash.match(/^#\/(\w+)/) || [])[1];
  const page = PAGES.includes(name) ? name : "overview";
  if (currentPage === "properties" && page !== "properties" && Object.keys(propEdits).length) {
    const leave = await confirmDialog({ title: "Уйти без сохранения?", body: `Несохранённых параметров: ${Object.keys(propEdits).length}.`, ok: "Уйти" });
    if (!leave) {
      history.replaceState(null, "", "#/properties");
      return;
    }
    propEdits = {};
  }
  currentPage = page;
  for (const section of document.querySelectorAll(".page")) section.hidden = section.dataset.page !== page;
  for (const link of document.querySelectorAll("#nav a")) {
    if (link.dataset.route === page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  if (page === "mods" && !state.server && state.connection) checkServer();
  if (page === "properties") {
    if (!state.props || state.props.error) loadProps();
    else renderProps();
  }
  if (page === "console") enterConsole();
  else leaveConsole();
  window.scrollTo(0, 0);
}

async function enterMain() {
  showScreen("main");
  try {
    await refreshAll();
  } catch (err) {
    toast(err.message, true);
  }
  route();
  await loadStatus();
  scheduleStatus();
}

// --- инициализация ---------------------------------------------------------

function onSegmented(id, fn) {
  $(id).addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (btn) fn(btn);
  });
}

function init() {
  fillLoaderSelects();
  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorEl = $("login-error");
    errorEl.hidden = true;
    try {
      const resp = await fetch("/api/v1/admin/login", jsonBody("POST", { password: $("login-password").value }));
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
  window.addEventListener("beforeunload", (e) => { if (Object.keys(propEdits).length) e.preventDefault(); });

  // строка статуса
  $("sb-actions").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (btn) serverAction(btn.dataset.action);
  });
  $("sb-refresh").addEventListener("click", loadStatus);

  // моды
  $("btn-add-mods").addEventListener("click", openAddDialog);
  $("btn-modrinth").addEventListener("click", openModrinth);
  $("mr-form").addEventListener("submit", searchModrinth);
  onSegmented("mr-type", (btn) => { mrType = btn.dataset.type; syncMrType(); });
  $("mods-search").addEventListener("input", renderMods);
  $("mods-search").addEventListener("keydown", (e) => {
    // Enter в пустой выдаче — сразу на Modrinth.
    if (e.key === "Enter" && !$("mods-list").querySelector(".mod")) openModrinth();
  });
  $("mods-all-versions").addEventListener("change", renderMods);
  onSegmented("mods-filter", (btn) => {
    modsFilter = btn.dataset.filter;
    for (const b of $("mods-filter").querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === btn));
    renderMods();
  });

  const dropzone = $("dropzone");
  const fileInput = $("file-input");
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
  fileInput.addEventListener("change", () => { addFiles(fileInput.files); fileInput.value = ""; });
  for (const ev of ["dragenter", "dragover"]) dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("over"); });
  for (const ev of ["dragleave", "drop"]) dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("over"); });
  dropzone.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));

  onSegmented("add-type-all", (btn) => {
    bulkType = btn.dataset.type;
    for (const item of queue) if (item.status === "idle" || item.status === "err") item.type = bulkType;
    syncBulkType();
    renderQueue();
  });
  $("add-loader").addEventListener("change", updateSubmit);
  $("add-mc_version").addEventListener("input", updateSubmit);
  $("add-submit").addEventListener("click", submitUpload);

  // редактирование мода
  $("edit-form").addEventListener("input", syncEdit);
  $("edit-form").addEventListener("change", syncEdit);
  $("edit-form").addEventListener("submit", saveEdit);
  onSegmented("edit-type", (btn) => { editing.type = btn.dataset.type; syncEdit(); });
  $("edit-cancel").addEventListener("click", () => $("dlg-edit").close());
  $("edit-close").addEventListener("click", () => $("dlg-edit").close());

  // консоль
  $("log-follow").addEventListener("change", syncLogFollow);
  $("rcon-form").addEventListener("submit", sendRcon);
  $("rcon-enable").addEventListener("click", enableRcon);

  // параметры игры
  $("props-search").addEventListener("input", renderProps);
  $("props-save").addEventListener("click", () => saveProps(false));
  $("props-save-restart").addEventListener("click", () => saveProps(true));
  $("props-reset").addEventListener("click", () => { propEdits = {}; renderProps(); });

  // подключение
  $("profile-form").addEventListener("input", () => { profileEdited = true; onProfileInput(); });
  $("profile-form").addEventListener("change", () => { profileEdited = true; onProfileInput(); });
  $("profile-form").addEventListener("submit", saveProfile);
  $("profile-reset").addEventListener("click", fillProfileForm);
  $("conn-form").addEventListener("submit", saveConnection);
  $("conn-protocol").addEventListener("change", onConnProtocol);
  $("conn-test").addEventListener("click", testConnection);
  $("conn-reset-key").addEventListener("click", () => saveConnection(null, { resetHostKey: true }));

  if (getToken()) enterMain();
  else showScreen("login");
}

init();
