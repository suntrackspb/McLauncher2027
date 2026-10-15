// Параметры server.properties ванильного Minecraft.
// since/until — версия, с которой параметр появился / в которой исчез (не включительно).
// Ключи, которых здесь нет (их добавляют моды, загрузчики, ядра), админка
// показывает из самого файла в группе «Прочее».

const PROP_GROUPS = [
  ["game", "Игра"],
  ["world", "Мир"],
  ["players", "Игроки и доступ"],
  ["perf", "Производительность"],
  ["network", "Сеть"],
  ["remote", "Удалённое управление"],
  ["pack", "Ресурспак"],
  ["other", "Прочее"],
];

const LEVELS = [["1", "1 — без защиты спавна"], ["2", "2 — командные блоки"], ["3", "3 — модерация"], ["4", "4 — всё, включая /stop"]];

const PROP_SCHEMA = [
  // Игра
  { key: "motd", mono: false, group: "game", type: "text", def: "A Minecraft Server", label: "Описание сервера", desc: "Строка под названием в списке серверов. Цвета — коды §." },
  { key: "gamemode", group: "game", type: "enum", def: "survival", label: "Режим игры", options: [["survival", "Выживание"], ["creative", "Творчество"], ["adventure", "Приключение"], ["spectator", "Наблюдение"]] },
  { key: "force-gamemode", group: "game", type: "bool", def: "false", label: "Сбрасывать режим при входе", desc: "Каждый вход переводит игрока в режим сервера." },
  { key: "difficulty", group: "game", type: "enum", def: "easy", label: "Сложность", options: [["peaceful", "Мирная"], ["easy", "Лёгкая"], ["normal", "Нормальная"], ["hard", "Сложная"]] },
  { key: "hardcore", group: "game", type: "bool", def: "false", label: "Хардкор", desc: "После смерти — только наблюдение." },
  { key: "pvp", group: "game", type: "bool", def: "true", label: "PvP", desc: "Игроки могут наносить урон друг другу." },
  { key: "allow-flight", group: "game", type: "bool", def: "false", label: "Разрешить полёт", desc: "Не кикать за полёт в выживании. Включите, если есть моды с джетпаками и крыльями." },
  { key: "enable-command-block", group: "game", type: "bool", def: "false", label: "Командные блоки" },
  { key: "spawn-monsters", group: "game", type: "bool", def: "true", label: "Монстры" },
  { key: "spawn-animals", group: "game", type: "bool", def: "true", label: "Животные", until: "1.21.2" },
  { key: "spawn-npcs", group: "game", type: "bool", def: "true", label: "Жители", until: "1.21.2" },
  { key: "allow-nether", group: "game", type: "bool", def: "true", label: "Незер" },

  // Мир
  { key: "level-name", group: "world", type: "text", def: "world", label: "Папка мира", desc: "Если такой папки нет, сервер создаст новый мир." },
  { key: "level-seed", group: "world", type: "text", def: "", label: "Сид", desc: "Используется только при создании мира. Пусто — случайный." },
  { key: "level-type", group: "world", type: "text", def: "minecraft:normal", label: "Тип мира", suggest: ["minecraft:normal", "minecraft:flat", "minecraft:large_biomes", "minecraft:amplified", "minecraft:single_biome_surface"], since: "1.19", desc: "Только при создании мира." },
  { key: "level-type", group: "world", type: "text", def: "default", label: "Тип мира", suggest: ["default", "flat", "largeBiomes", "amplified", "buffet"], until: "1.19", desc: "Только при создании мира." },
  { key: "generator-settings", group: "world", type: "text", def: "{}", label: "Настройки генератора", desc: "JSON для плоского мира и других типов." },
  { key: "generate-structures", group: "world", type: "bool", def: "true", label: "Строения", desc: "Деревни, крепости и прочее в новых чанках." },
  { key: "max-world-size", group: "world", type: "int", def: "29999984", min: 1, max: 29999984, label: "Радиус мира", desc: "В блоках от центра." },
  { key: "spawn-protection", group: "world", type: "int", def: "16", min: 0, label: "Защита спавна", desc: "Радиус, где строят только операторы. 0 — без защиты." },
  { key: "max-build-height", group: "world", type: "int", def: "256", min: 1, label: "Предел высоты", until: "1.17" },
  { key: "initial-enabled-packs", group: "world", type: "text", def: "vanilla", label: "Датапаки нового мира", since: "1.19.3", desc: "Через запятую, например vanilla,update_1_20." },
  { key: "initial-disabled-packs", group: "world", type: "text", def: "", label: "Выключенные датапаки нового мира", since: "1.19.3" },
  { key: "region-file-compression", group: "world", type: "enum", def: "deflate", label: "Сжатие регионов", since: "1.20.5", options: [["deflate", "deflate — по умолчанию"], ["lz4", "lz4 — быстрее, файлы больше"], ["none", "без сжатия"]] },

  // Игроки и доступ
  { key: "max-players", group: "players", type: "int", def: "20", min: 0, label: "Максимум игроков" },
  { key: "white-list", group: "players", type: "bool", def: "false", label: "Белый список", desc: "Заходят только игроки из whitelist.json." },
  { key: "enforce-whitelist", group: "players", type: "bool", def: "false", label: "Кикать не из списка", desc: "При перезагрузке списка выкидывать тех, кого в нём нет." },
  { key: "online-mode", group: "players", type: "bool", def: "true", label: "Проверка аккаунтов", desc: "Сервер проверяет игрока через сервер авторизации." },
  { key: "enforce-secure-profile", group: "players", type: "bool", def: "true", label: "Подписанный чат", since: "1.19", desc: "Пускать только игроков с ключом подписи чата." },
  { key: "prevent-proxy-connections", group: "players", type: "bool", def: "false", label: "Блокировать прокси", desc: "Кикать, если IP входа не совпадает с IP авторизации." },
  { key: "player-idle-timeout", group: "players", type: "int", def: "0", min: 0, label: "Кик за бездействие", desc: "Минуты. 0 — не кикать." },
  { key: "op-permission-level", group: "players", type: "enum", def: "4", label: "Права операторов", options: LEVELS },
  { key: "function-permission-level", group: "players", type: "enum", def: "2", label: "Права функций датапаков", options: LEVELS, since: "1.14.4" },
  { key: "hide-online-players", group: "players", type: "bool", def: "false", label: "Скрывать список онлайна", since: "1.18" },
  { key: "log-ips", group: "players", type: "bool", def: "true", label: "Писать IP в лог", since: "1.20.2" },
  { key: "text-filtering-config", group: "players", type: "text", def: "", label: "Фильтр чата", since: "1.16.4" },
  { key: "text-filtering-version", group: "players", type: "int", def: "0", min: 0, label: "Версия фильтра чата", since: "1.21.2" },

  // Производительность
  { key: "view-distance", group: "perf", type: "int", def: "10", min: 2, max: 32, label: "Дальность прорисовки", desc: "В чанках. Сильнее всего влияет на нагрузку." },
  { key: "simulation-distance", group: "perf", type: "int", def: "10", min: 3, max: 32, label: "Дальность симуляции", since: "1.18", desc: "В чанках вокруг игрока работают мобы, механизмы и рост растений." },
  { key: "entity-broadcast-range-percentage", group: "perf", type: "int", def: "100", min: 10, max: 1000, label: "Видимость сущностей", since: "1.16", desc: "Процент от стандартной дальности." },
  { key: "max-tick-time", group: "perf", type: "int", def: "60000", min: -1, label: "Сторож зависания", desc: "Мс на тик, после которых сервер считается зависшим и падает. −1 — выключить; полезно для тяжёлых модпаков." },
  { key: "max-chained-neighbor-updates", group: "perf", type: "int", def: "1000000", label: "Предел цепочки обновлений блоков", since: "1.19" },
  { key: "pause-when-empty-seconds", group: "perf", type: "int", def: "60", min: 0, label: "Пауза без игроков", since: "1.21.2", desc: "Через сколько секунд без игроков остановить тики. 0 — не останавливать." },
  { key: "sync-chunk-writes", group: "perf", type: "bool", def: "true", label: "Синхронная запись чанков", since: "1.16", desc: "Надёжнее при сбоях, но медленнее." },
  { key: "network-compression-threshold", group: "perf", type: "int", def: "256", min: -1, label: "Порог сжатия пакетов", desc: "Байты. −1 — без сжатия." },
  { key: "use-native-transport", group: "perf", type: "bool", def: "true", label: "Нативный сетевой стек", desc: "Только Linux." },
  { key: "enable-jmx-monitoring", group: "perf", type: "bool", def: "false", label: "JMX-мониторинг", since: "1.16" },
  { key: "snooper-enabled", group: "perf", type: "bool", def: "true", label: "Отправлять статистику Mojang", until: "1.18" },

  // Сеть
  { key: "server-ip", group: "network", type: "text", def: "", label: "IP для прослушивания", desc: "Обычно пусто — сервер слушает все адреса." },
  { key: "server-port", group: "network", type: "int", def: "25565", min: 1, max: 65535, label: "Порт" },
  { key: "rate-limit", group: "network", type: "int", def: "0", min: 0, label: "Лимит пакетов", since: "1.16", desc: "Пакетов в секунду до кика. 0 — без лимита." },
  { key: "enable-status", group: "network", type: "bool", def: "true", label: "Показывать в списке серверов", since: "1.16", desc: "Если выключить, сервер будет выглядеть офлайн, но зайти можно." },
  { key: "accepts-transfers", group: "network", type: "bool", def: "false", label: "Принимать переводы", since: "1.20.5", desc: "Разрешить вход через /transfer с других серверов." },
  { key: "bug-report-link", group: "network", type: "text", def: "", label: "Ссылка для жалоб", since: "1.21" },

  // Удалённое управление
  { key: "enable-rcon", group: "remote", type: "bool", def: "false", label: "RCON", desc: "Нужен для консоли в админке." },
  { key: "rcon.port", group: "remote", type: "int", def: "25575", min: 1, max: 65535, label: "Порт RCON" },
  { key: "rcon.password", group: "remote", type: "secret", def: "", label: "Пароль RCON" },
  { key: "broadcast-rcon-to-ops", group: "remote", type: "bool", def: "true", label: "Показывать RCON-команды операторам" },
  { key: "broadcast-console-to-ops", group: "remote", type: "bool", def: "true", label: "Показывать консольные команды операторам" },
  { key: "enable-query", group: "remote", type: "bool", def: "false", label: "Query", desc: "Протокол GameSpy4 для мониторингов." },
  { key: "query.port", group: "remote", type: "int", def: "25565", min: 1, max: 65535, label: "Порт Query" },
  { key: "management-server-enabled", group: "remote", type: "bool", def: "false", label: "Management API", since: "1.21.9" },
  { key: "management-server-host", group: "remote", type: "text", def: "localhost", label: "Адрес Management API", since: "1.21.9" },
  { key: "management-server-port", group: "remote", type: "int", def: "0", min: 0, max: 65535, label: "Порт Management API", since: "1.21.9" },

  // Ресурспак
  { key: "resource-pack", group: "pack", type: "text", def: "", label: "Ссылка на ресурспак", desc: "Прямая ссылка на zip." },
  { key: "resource-pack-sha1", group: "pack", type: "text", def: "", label: "SHA-1 ресурспака", desc: "Чтобы клиент перекачивал пак при обновлении." },
  { key: "resource-pack-id", group: "pack", type: "text", def: "", label: "UUID ресурспака", since: "1.20.3" },
  { key: "require-resource-pack", group: "pack", type: "bool", def: "false", label: "Обязательный ресурспак", since: "1.17", desc: "Кто откажется — не зайдёт." },
  { key: "resource-pack-prompt", mono: false, group: "pack", type: "text", def: "", label: "Текст запроса ресурспака", since: "1.17" },
];

// "1.20.1" → [1, 20, 1]; снапшоты и прочее → null (покажем всё).
function parseMcVersion(v) {
  const m = /^(\d+)\.(\d+)(?:\.(\d+))?$/.exec((v || "").trim());
  return m ? [Number(m[1]), Number(m[2]), Number(m[3] || 0)] : null;
}

function cmpVersion(a, b) {
  for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] - b[i];
  return 0;
}

function propAppliesTo(prop, version) {
  if (!version) return !prop.until; // версия неизвестна — показываем актуальные
  if (prop.since && cmpVersion(version, parseMcVersion(prop.since)) < 0) return false;
  if (prop.until && cmpVersion(version, parseMcVersion(prop.until)) >= 0) return false;
  return true;
}
