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
  const SKY = [
    [0, [14, 20, 54]],
    [0.4, [52, 44, 118]],
    [0.72, [190, 98, 112]],
    [1, [252, 176, 92]],
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
    return "rgb(252,176,92)";
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

  // квадратное закатное солнце
  const sx = Math.floor(W * 0.7);
  const sy = Math.floor(H * 0.52);
  [[34, 0.1], [24, 0.14], [14, 1]].forEach(([size, alpha], i) => {
    s.fillStyle = i === 2 ? "#fff1b0" : `rgba(255, 214, 140, ${alpha})`;
    s.fillRect(sx - size / 2, sy - size / 2, size, size);
  });

  // холмы тремя слоями, колонки по 4 пикселя
  const hills = layer();
  const h = hills.getContext("2d");

  function ridge(base, amp, color, phase, snow) {
    for (let x = 0; x < W; x += 4) {
      const wave = Math.sin(x * 0.021 + phase) * amp + Math.sin(x * 0.057 + phase * 2) * amp * 0.45;
      const top = Math.round((base + wave) / 2) * 2;
      h.fillStyle = color;
      h.fillRect(x, top, 4, H - top);
      if (snow) {
        h.fillStyle = snow;
        h.fillRect(x, top, 4, 2);
      }
    }
  }

  // ель ярусами, на каждом ярусе снег
  function tree(x, y) {
    h.fillStyle = "#4b3320";
    h.fillRect(x, y - 3, 2, 3);
    const tiers = [[8, y - 7], [6, y - 11], [4, y - 15], [2, y - 18]];
    for (const [w, ty] of tiers) {
      h.fillStyle = "#1c4a3a";
      h.fillRect(x + 1 - w / 2, ty, w, 4);
      h.fillStyle = "#dfe8f6";
      h.fillRect(x + 1 - w / 2 + 1, ty, Math.max(2, w - 2), 1);
    }
  }

  ridge(horizon - 30, 8, "#3a3a7c", 1.2, "#8e8dc4");
  ridge(horizon - 14, 7, "#2b4f63", 3.1, "#a9bfd4");
  for (let x = 14; x < W; x += 12 + Math.floor(r() * 22)) {
    const wave = Math.sin(x * 0.021 + 3.1) * 7 + Math.sin(x * 0.057 + 6.2) * 3.15;
    tree(x, Math.round((horizon - 14 + wave) / 2) * 2 + 1);
  }
  ridge(horizon + 12, 4, "#4d6a86", 5.3, "#c9d8ea");

  // передний план: трава и земля
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
      ctx.fillStyle = "rgba(255, 214, 210, 0.5)";
      ctx.fillRect(x, c.y, c.w, 4);
      ctx.fillRect(x + 4, c.y - 3, c.w - 12, 3);
      ctx.fillStyle = "rgba(255, 238, 230, 0.35)";
      ctx.fillRect(x + 2, c.y + 4, c.w - 6, 2);
    }

    ctx.drawImage(hills, 0, 0);

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
