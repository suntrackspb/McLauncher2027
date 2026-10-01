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
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) dot(g, x, y, pick(r, GRASS));
    }),
    dirt: texture(23, (g, r, n) => {
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) dot(g, x, y, pick(r, DIRT));
    }),
    "grass-side": texture(37, (g, r, n) => {
      for (let x = 0; x < n; x++) {
        const depth = 3 + (r() < 0.55 ? 1 : 0) + (r() < 0.25 ? 2 : 0);
        for (let y = 0; y < n; y++) dot(g, x, y, y < depth ? pick(r, GRASS) : pick(r, DIRT));
      }
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

  function ridge(base, amp, color, phase) {
    h.fillStyle = color;
    for (let x = 0; x < W; x += 4) {
      const wave = Math.sin(x * 0.021 + phase) * amp + Math.sin(x * 0.057 + phase * 2) * amp * 0.45;
      const top = Math.round((base + wave) / 2) * 2;
      h.fillRect(x, top, 4, H - top);
    }
  }

  function tree(x, y) {
    h.fillStyle = "#4b3320";
    h.fillRect(x, y - 6, 2, 6);
    h.fillStyle = "#1f5a2a";
    h.fillRect(x - 3, y - 12, 8, 6);
    h.fillStyle = "#2a7a38";
    h.fillRect(x - 1, y - 15, 4, 3);
    h.fillRect(x - 3, y - 12, 3, 2);
  }

  ridge(horizon - 30, 8, "#3a3a7c", 1.2);
  ridge(horizon - 14, 7, "#2b4f63", 3.1);
  for (let x = 14; x < W; x += 12 + Math.floor(r() * 22)) {
    const wave = Math.sin(x * 0.021 + 3.1) * 7 + Math.sin(x * 0.057 + 6.2) * 3.15;
    tree(x, Math.round((horizon - 14 + wave) / 2) * 2 + 1);
  }
  ridge(horizon + 12, 4, "#2d6b34", 5.3);

  // передний план: трава и земля
  const groundTop = H - 22;
  for (let y = groundTop; y < H; y++) {
    for (let x = 0; x < W; x++) {
      h.fillStyle = y < groundTop + 3 ? pick(r, GRASS) : pick(r, DIRT);
      h.fillRect(x, y, 1, 1);
    }
  }
  for (let x = 0; x < W; x++) {
    if (r() < 0.35) {
      h.fillStyle = pick(r, GRASS);
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
