/**
 * Flujo crítico Fase 1: Ventas (Personalizar + agregado), Comandera, sidebar.
 *
 *   cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
 *   cd frontend && npm run build && npm run test:estabilidad-critico
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, "../../docs/screenshots/estabilidad");
const BASE_URL = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const API_URL = process.env.API_URL || "http://127.0.0.1:8000";
const LOGIN_USER = process.env.CAPTURE_LOGIN || "admin";
const LOGIN_PASS = process.env.CAPTURE_PASSWORD || "admin123";

const VIEWPORTS = [
  { w: 390, h: 844, tag: "390x844" },
  { w: 768, h: 1024, tag: "768x1024" },
  { w: 1024, h: 600, tag: "1024x600" },
  { w: 1366, h: 768, tag: "1366x768" },
];

async function waitForUrl(url, timeoutMs = 90000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Servicio no disponible: ${url}`);
}

function startPreview() {
  return spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", "4173"], {
    cwd: path.resolve(__dirname, ".."),
    shell: true,
    stdio: "ignore",
    detached: process.platform !== "win32",
  });
}

async function login(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: "load" });
  await page.waitForSelector("#user", { timeout: 15000 });
  await page.fill("#user", LOGIN_USER);
  await page.fill("#pass", LOGIN_PASS);
  await page.getByRole("button", { name: /Entrar al sistema/i }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 20000 });
  await page.waitForSelector(".app-shell", { timeout: 20000 });
}

async function assertSidebar(page, vp) {
  await page.setViewportSize({ width: vp.w, height: vp.h });
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await page.waitForSelector(".app-shell", { timeout: 15000 });

  if (vp.w < 768) {
    const menuBtn = page.locator(".navbar__menu-btn");
    if (!(await menuBtn.isVisible())) {
      throw new Error(`[${vp.tag}] hamburguesa no visible`);
    }
    await menuBtn.click({ force: true });
    await page.waitForSelector(".sidebar--open", { timeout: 5000 });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(250);
    if ((await page.locator(".sidebar--open").count()) > 0) {
      throw new Error(`[${vp.tag}] sidebar no cerró`);
    }
  } else {
    const nav = page.locator(".sidebar__nav");
    await nav.waitFor({ state: "visible", timeout: 10000 });
    const overflowY = await nav.evaluate((el) => getComputedStyle(el).overflowY);
    if (!/auto|scroll/.test(overflowY)) {
      throw new Error(`[${vp.tag}] sidebar nav sin scroll (overflow=${overflowY})`);
    }
  }
  console.log(`OK sidebar ${vp.tag}`);
}

async function main() {
  const health = await fetch(`${API_URL}/health`).then((r) => r.json()).catch(() => null);
  if (!health || health.status !== "ok") {
    throw new Error(`API no disponible en ${API_URL}`);
  }

  let previewProc;
  try {
    await waitForUrl(BASE_URL, 3000);
  } catch {
    previewProc = startPreview();
    await waitForUrl(BASE_URL);
  }

  await mkdir(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("dialog", (dialog) => dialog.accept());

  await login(page);

  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(`${BASE_URL}/ventas`, { waitUntil: "load" });
  await page.waitForSelector(".ventas-workspace, .page", { timeout: 15000 });
  const mesa = page.locator(".mesa-btn, button").filter({ hasText: /^1$/ }).first();
  if (await mesa.count()) {
    await mesa.click();
    await page.waitForTimeout(400);
  }
  const personalizar = page.locator(".ventas-producto-item__personalizar").first();
  if (!(await personalizar.count())) {
    throw new Error("No hay botón Personalizar en el catálogo");
  }
  const box = await personalizar.boundingBox();
  if (!box || box.width < 44 || box.height < 44) {
    throw new Error(`Personalizar no cumple 44×44 (actual ${box?.width}×${box?.height})`);
  }
  await personalizar.click();
  await page.waitForSelector(".modal-box", { timeout: 8000 });
  const modalText = await page.locator(".modal-box").innerText();
  if (!/Cantidad|Comentario/i.test(modalText)) {
    throw new Error("Modal Personalizar no muestra cantidad/comentario");
  }
  await page.screenshot({ path: path.join(OUT_DIR, "ventas-personalizar.png") });
  await page.getByRole("button", { name: /Cancelar/i }).click();
  console.log("OK Personalizar abre modal sin agregar");

  await page.goto(`${BASE_URL}/comandera`, { waitUntil: "load" });
  await page.waitForSelector(".comandera-page, .page", { timeout: 15000 });
  await page.screenshot({ path: path.join(OUT_DIR, "comandera.png") });
  console.log("OK Comandera");

  for (const vp of VIEWPORTS) {
    await assertSidebar(page, vp);
    await page.screenshot({ path: path.join(OUT_DIR, `sidebar-${vp.tag}.png`) });
  }

  await browser.close();
  if (previewProc?.pid) {
    try {
      process.kill(previewProc.pid);
    } catch {
      /* ignore */
    }
  }
  console.log(`Capturas en ${OUT_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
