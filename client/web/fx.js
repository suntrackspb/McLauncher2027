"use strict";

/**
 * Графика без внешних файлов: пиксельные текстуры блоков, 3D-кубы и
 * фоновая сцена рисуются на canvas, чтобы приложение паковалось офлайн.
 */
(function () {
  function rng(seed) {
    let s = seed >>> 0;
    return () => {
      s = (s * 1664525 + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }

  const pick = (r, list) => list[Math.floor(r() * list.length)];

  const GRASS = ["#5f9f35", "#6bb23c", "#549030", "#7bc44a", "#4f8a2d"];
  const DIRT = ["#86592f", "#79502b", "#946238", "#6e4727", "#8b5e34"];
  const STONE = ["#7f7f7f", "#8a8a8a", "#757575", "#6c6c6c", "#939393"];
  const PLANK = ["#a8793f", "#9c6e38", "#b2824a", "#946636"];
  const SNOW = ["#f4f8ff", "#e6eef9", "#ffffff", "#dbe6f5", "#eef3fb"];
  const ICE = ["#8fc1ef", "#7fb3e6", "#9dccf5", "#73a7dd", "#a9d4f7"];

  function texture(seed, paint) {
    const size = 16;
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const g = c.getContext("2d");
    paint(g, rng(seed), size);
    return c.toDataURL();
  }

  function dot(g, x, y, color) {
    g.fillStyle = color;
    g.fillRect(x, y, 1, 1);
  }

  const textures = {
    "grass-top": texture(11, (g, r, n) => {
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) dot(g, x, y, pick(r, SNOW));
    }),
    dirt: texture(23, (g, r, n) => {
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) dot(g, x, y, pick(r, DIRT));
    }),
    "grass-side": texture(37, (g, r, n) => {
      for (let x = 0; x < n; x++) {
        // блок травы, засыпанный снегом: белая шапка, под ней полоска травы
        const depth = 3 + (r() < 0.55 ? 1 : 0) + (r() < 0.25 ? 2 : 0);
        for (let y = 0; y < n; y++) {
          const c = y < depth ? pick(r, SNOW) : y === depth ? pick(r, GRASS) : pick(r, DIRT);
          dot(g, x, y, c);
        }
      }
    }),
    ice: texture(67, (g, r, n) => {
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) dot(g, x, y, pick(r, ICE));
      // трещины-блики плотного льда
      for (let i = 0; i < 5; i++) dot(g, (i * 7 + 2) % n, (i * 5 + 3) % n, "#d6ecff");
      for (let i = 0; i < 4; i++) dot(g, (i * 11 + 5) % n, (i * 3 + 9) % n, "#5f93c8");
    }),
    stone: texture(41, (g, r, n) => {
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) dot(g, x, y, pick(r, STONE));
    }),
    planks: texture(53, (g, r, n) => {
      for (let y = 0; y < n; y++) {
        for (let x = 0; x < n; x++) {
          const seam = y % 4 === 3;
          dot(g, x, y, seam ? "#7a5128" : pick(r, PLANK));
        }
      }
      for (let y = 0; y < n; y += 4) dot(g, (y * 5 + 3) % n, y, "#7a5128");
    }),
  };

  // снежная шапка 16×6 с неровным нижним краем-«сосульками»
  textures["snow-cap"] = (() => {
    const c = document.createElement("canvas");
    c.width = 16;
    c.height = 6;
    const g = c.getContext("2d");
    const r = rng(83);
    for (let x = 0; x < 16; x++) {
      const depth = 2 + Math.floor(r() * 3) + (r() < 0.15 ? 1 : 0);
      for (let y = 0; y < depth; y++) dot(g, x, y, y === depth - 1 ? "#cfdcef" : pick(r, SNOW));
    }
    return c.toDataURL();
  })();

  const root = document.documentElement;
  for (const [name, url] of Object.entries(textures)) {
    root.style.setProperty(`--tex-${name}`, `url(${url})`);
  }

  // ---- 3D-кубы: шесть граней внутри каждого .cube ----
  document.querySelectorAll(".cube").forEach((cube) => {
    cube.innerHTML = ["front", "back", "right", "left", "top", "bottom"]
      .map((f) => `<i class="face ${f}"></i>`)
      .join("");
  });

  // ---- Гирлянда под кнопкой «Играть» ----
  const garland = document.querySelector(".garland");
  if (garland) {
    const colors = ["#ff4d5a", "#ffd25a", "#5ee08a", "#5ab4ff"];
    garland.innerHTML = Array.from({ length: 11 }, (_, i) =>
      `<i class="bulb" style="--c:${colors[i % 4]};--i:${i}"></i>`
    ).join("");
  }

  // ---- Фоновая сцена ----
  const canvas = document.getElementById("scene");
  if (!canvas) return;

  const W = 320;
  const H = 180;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  const r = rng(2027);
  const horizon = Math.floor(H * 0.74);

  function layer() {
    const c = document.createElement("canvas");
    c.width = W;
    c.height = H;
    return c;
  }

  const lerp = (a, b, t) => a + (b - a) * t;
  // Биом «снежная тундра»: холодные сумерки — глубокий синий уходит в
  // бирюзу и бледную полосу у горизонта.
  const SKY = [
    [0, [10, 22, 56]],
    [0.42, [28, 70, 118]],
    [0.78, [96, 152, 186]],
    [1, [206, 224, 236]],
  ];

  function skyColor(t) {
    for (let i = 1; i < SKY.length; i++) {
      if (t <= SKY[i][0]) {
        const [t0, c0] = SKY[i - 1];
        const [t1, c1] = SKY[i];
        const k = (t - t0) / (t1 - t0);
        return `rgb(${c0.map((v, j) => Math.round(lerp(v, c1[j], k))).join(",")})`;
      }
    }
    return "rgb(206,224,236)";
  }

  // небо ступенчатыми полосами, как в игре
  const sky = layer();
  const s = sky.getContext("2d");
  const bands = 34;
  for (let i = 0; i < bands; i++) {
    s.fillStyle = skyColor(i / (bands - 1));
    const y0 = Math.floor((i * horizon) / bands);
    s.fillRect(0, y0, W, Math.ceil(horizon / bands) + 1);
  }
  s.fillStyle = skyColor(1);
  s.fillRect(0, horizon, W, H - horizon);

  // низкое бледное солнце полярного дня
  const sx = Math.floor(W * 0.78);
  const sy = Math.floor(H * 0.4);
  [[36, 0.08], [24, 0.14], [12, 1]].forEach(([size, alpha], i) => {
    s.fillStyle = i === 2 ? "#f4fbff" : `rgba(220, 240, 255, ${alpha})`;
    s.fillRect(sx - size / 2, sy - size / 2, size, size);
  });

  const land = layer();
  const h = land.getContext("2d");
  const rect = (color, x, y, w, hgt) => {
    h.fillStyle = color;
    h.fillRect(x, y, w, hgt);
  };

  // дальние горы: зубчатые блоки по 4 пикселя, верх в снегу
  function mountains(base, amp, color, cap, phase) {
    for (let x = 0; x < W; x += 4) {
      const peak = Math.abs(Math.sin(x * 0.013 + phase)) * amp + Math.sin(x * 0.07 + phase) * 3;
      const top = Math.round((base - peak) / 2) * 2;
      rect(color, x, top, 4, H - top);
      if (peak > amp * 0.45) rect(cap, x, top, 4, peak > amp * 0.8 ? 6 : 4);
    }
  }

  // равнина тундры — почти плоская, перепады ровно на «блок» (2 пикселя)
  function plain(base, color, edge, seed) {
    const pr = rng(seed);
    let y = base;
    for (let x = 0; x < W; x += 8) {
      if (pr() < 0.3) y = base + (pr() < 0.5 ? -2 : 2);
      rect(color, x, y, 8, H - y);
      rect(edge, x, y, 8, 1);
    }
  }

  // ель ярусами, на каждом ярусе снег
  function tree(x, y, size = 1) {
    rect("#3d2a1c", x, y - 3, 2, 3);
    const tiers = size > 1 ? [[10, 7], [8, 11], [6, 15], [4, 19], [2, 22]] : [[8, 7], [6, 11], [4, 15], [2, 18]];
    for (const [w, dy] of tiers) {
      rect("#173f39", x + 1 - w / 2, y - dy, w, 4);
      rect("#e6eef8", x + 2 - w / 2, y - dy, Math.max(2, w - 2), 1);
    }
  }

  // ледяной шип: столб плотного льда, сужается ступенями, слева блик
  function iceSpike(x, base, height, width) {
    let w = width;
    let y = base;
    const step = Math.max(6, Math.floor(height / (width / 2 + 1)));
    while (w > 0 && y > base - height) {
      const top = Math.max(base - height, y - step);
      const left = x - Math.floor(w / 2);
      rect("#8cc4ee", left, top, w, y - top);
      rect("#d4ecff", left, top, Math.max(1, Math.floor(w / 3)), y - top);
      rect("#5e96cc", left + w - 1, top, 1, y - top);
      y = top;
      w -= 2;
    }
  }

  // иглу: купол из снежных блоков с тёмным входом
  function igloo(x, y) {
    const rows = [[24, 0], [26, 3], [26, 6], [24, 9], [20, 12], [12, 15]];
    rows.forEach(([w, dy], i) => rect(i % 2 ? "#e8f0fa" : "#d2deec", x - w / 2, y - dy - 3, w, 3));
    rect("#1d2b44", x + 4, y - 8, 6, 8);
    rect("#3a4d6c", x + 4, y - 8, 6, 1);
    rect("#a9bcd4", x - 12, y - 1, 24, 1);
  }

  mountains(horizon - 6, 34, "#5a76a8", "#e2ecf7", 0.6);
  mountains(horizon + 4, 18, "#46628f", "#cbd9ea", 2.4);

  const farPlain = horizon + 6;
  plain(farPlain, "#9fb6cf", "#e4edf7", 7);
  for (const x of [22, 58, 96, 214, 262, 300]) tree(x, farPlain + 1);

  // ледяные шипы стоят по краям, центр кадра свободен под кнопку
  iceSpike(42, farPlain + 14, 92, 16);
  iceSpike(64, farPlain + 14, 48, 10);
  iceSpike(22, farPlain + 14, 34, 8);
  iceSpike(282, farPlain + 14, 80, 14);
  iceSpike(304, farPlain + 14, 40, 8);

  const nearPlain = horizon + 14;
  plain(nearPlain, "#c4d4e6", "#f2f7fc", 19);

  // замёрзшее озеро: лёд с бликами, утоплен в ближнюю равнину
  const lakeX = 112;
  const lakeW = 96;
  rect("#7fb2dc", lakeX, nearPlain + 4, lakeW, 10);
  rect("#a9d2f2", lakeX, nearPlain + 4, lakeW, 2);
  rect("#6a9fcd", lakeX + 4, nearPlain + 12, lakeW - 8, 2);
  for (const [dx, dy, w] of [[10, 6, 14], [40, 8, 22], [70, 6, 10], [24, 10, 8]]) {
    rect("#d8eeff", lakeX + dx, nearPlain + dy, w, 1);
  }

  igloo(246, nearPlain + 6);
  tree(84, nearPlain + 4, 2);
  tree(232, nearPlain + 2, 2);

  // передний план: снежный блок травы — снег, полоска травы, земля
  const groundTop = H - 22;
  for (let y = groundTop; y < H; y++) {
    for (let x = 0; x < W; x++) {
      h.fillStyle = y < groundTop + 3 ? pick(r, SNOW) : y === groundTop + 3 ? pick(r, GRASS) : pick(r, DIRT);
      h.fillRect(x, y, 1, 1);
    }
  }
  for (let x = 0; x < W; x++) {
    if (r() < 0.35) {
      h.fillStyle = pick(r, SNOW);
      h.fillRect(x, groundTop - 1, 1, 1);
    }
  }

  const stars = Array.from({ length: 46 }, () => ({
    x: Math.floor(r() * W),
    y: Math.floor(r() * horizon * 0.5),
    phase: r() * 6.28,
  }));

  const clouds = Array.from({ length: 6 }, (_, i) => ({
    x: r() * W,
    y: 14 + Math.floor(r() * 56),
    w: 22 + Math.floor(r() * 26),
    speed: 2 + r() * 3,
    row: i,
  }));

  // снегопад: ближние хлопья крупнее и быстрее
  const flakes = Array.from({ length: 140 }, () => {
    const near = r() < 0.25;
    return {
      x: r() * W,
      y: r() * H,
      size: near ? 2 : 1,
      speed: near ? 14 + r() * 8 : 5 + r() * 6,
      sway: r() * 6.28,
      alpha: near ? 0.95 : 0.5 + r() * 0.35,
    };
  });

  function draw(t) {
    ctx.drawImage(sky, 0, 0);

    for (const star of stars) {
      const a = 0.35 + 0.65 * Math.abs(Math.sin(t * 0.0012 + star.phase));
      ctx.fillStyle = `rgba(255,255,255,${a})`;
      ctx.fillRect(star.x, star.y, 1, 1);
    }

    for (const c of clouds) {
      const x = ((c.x + (t / 1000) * c.speed) % (W + 60)) - 40;
      ctx.fillStyle = "rgba(226, 238, 250, 0.45)";
      ctx.fillRect(x, c.y, c.w, 4);
      ctx.fillRect(x + 4, c.y - 3, c.w - 12, 3);
      ctx.fillStyle = "rgba(240, 248, 255, 0.3)";
      ctx.fillRect(x + 2, c.y + 4, c.w - 6, 2);
    }

    ctx.drawImage(land, 0, 0);

    const sec = t / 1000;
    for (const f of flakes) {
      const y = (f.y + sec * f.speed) % (H + 4) - 2;
      const x = (f.x + Math.sin(sec * 0.8 + f.sway) * 3 + sec * 2 + W) % W;
      ctx.fillStyle = `rgba(255,255,255,${f.alpha})`;
      ctx.fillRect(Math.round(x), Math.round(y), f.size, f.size);
    }
  }

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  draw(0);
  if (!reduced) {
    let last = 0;
    const tick = (t) => {
      if (t - last > 60) {
        last = t;
        draw(t);
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
})();
