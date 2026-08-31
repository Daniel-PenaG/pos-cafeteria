/**
 * Capturas responsive con Playwright contra build de producción.
 *
 * Modo recomendado (API real, catálogo demo local):
 *   Terminal 1: cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
 *   Terminal 2:
 *     cd frontend
 *     set VITE_API_URL=http://127.0.0.1:8000   # PowerShell: $env:VITE_API_URL=...
 *     npm run build
 *     npm run preview -- --host 127.0.0.1 --port 4173
 *   Terminal 3:
 *     set CAPTURE_REAL_API=1
 *     npm run capture:responsive
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, "../../docs/screenshots/responsive");
const BASE_URL = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const API_URL = process.env.API_URL || "http://127.0.0.1:8000";
const USE_REAL_API = process.env.CAPTURE_REAL_API !== "0";
const LOGIN_USER = process.env.CAPTURE_LOGIN || "admin";
const LOGIN_PASS = process.env.CAPTURE_PASSWORD || "admin123";

const VIEWPORTS = [
  { w: 320, h: 568, tag: "320x568" },
  { w: 360, h: 800, tag: "360x800" },
  { w: 390, h: 844, tag: "390x844" },
  { w: 412, h: 915, tag: "412x915" },
  { w: 768, h: 1024, tag: "768x1024" },
  { w: 1024, h: 768, tag: "1024x768" },
  { w: 1366, h: 768, tag: "1366x768" },
];

async function waitForUrl(url, timeoutMs = 60000) {
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

async function waitAppReady(page, { mobile = false } = {}) {
  await page.waitForSelector(".app-shell", { timeout: 30000 });
  if (mobile) {
    await page
      .waitForSelector(".navbar__menu-btn", { timeout: 15000 })
      .catch(() => page.waitForSelector(".app-content", { timeout: 5000 }));
  } else {
    await page.waitForSelector(".app-content", { timeout: 15000 });
  }
  await page.waitForTimeout(600);
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

async function ensureLoggedIn(page) {
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  if (page.url().includes("/login")) {
    await login(page);
  }
  await waitAppReady(page, { mobile: page.viewportSize().width < 768 });
}

async function shot(page, dir, name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true });
  await page.evaluate(() => window.scrollTo(0, 0));
}

async function captureMobile(page, vp) {
  const dir = path.join(OUT_DIR, vp.tag);
  await mkdir(dir, { recursive: true });
  await page.setViewportSize({ width: vp.w, height: vp.h });
  await ensureLoggedIn(page);

  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await shot(page, dir, "menu-closed");

  await page.locator(".navbar__menu-btn").click({ force: true });
  await page.waitForSelector(".sidebar--open", { timeout: 5000 });
  await page.waitForTimeout(400);
  await shot(page, dir, "menu-open");
  await page.locator(".sidebar__close").click({ force: true });
  await page.waitForTimeout(300);

  await page.goto(`${BASE_URL}/promociones`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await shot(page, dir, "promociones");

  const nuevaBtn = page.getByRole("button", { name: "Nueva promoción" });
  if (await nuevaBtn.count()) {
    await nuevaBtn.click();
    await page.waitForSelector(".modal-box", { timeout: 8000 });
    await page.waitForTimeout(300);
    await shot(page, dir, "promociones-modal");
    await page.locator(".modal-overlay").click({ position: { x: 5, y: 5 } }).catch(() => {});
    await page.waitForTimeout(200);
  }

  await page.goto(`${BASE_URL}/ventas`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  const mesa = page.locator(".mesa-card").first();
  if (await mesa.count()) {
    await mesa.click({ force: true });
    await page.waitForTimeout(1000);
    const producto = page.locator(".ventas-producto-item").first();
    if (await producto.count()) {
      await producto.click({ force: true });
      await page.waitForTimeout(800);
    }
  }
  await shot(page, dir, "ventas");

  await page.goto(`${BASE_URL}/comandera`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await shot(page, dir, "comandera");

  await page.goto(`${BASE_URL}/reportes`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await shot(page, dir, "reportes");

  await page.goto(`${BASE_URL}/usuarios`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await shot(page, dir, "usuarios");

  await page.goto(`${BASE_URL}/cuentas-cajero`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await shot(page, dir, "cuentas-cajero");
}

async function captureTabletDesktop(page, vp, name) {
  const dir = path.join(OUT_DIR, vp.tag);
  await mkdir(dir, { recursive: true });
  await page.setViewportSize({ width: vp.w, height: vp.h });
  await ensureLoggedIn(page);
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: false });
  await shot(page, dir, name);
  await page.goto(`${BASE_URL}/reportes`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: false });
  await shot(page, dir, `${name}-reportes`);
}

async function main() {
  if (USE_REAL_API) {
    await waitForUrl(`${API_URL}/docs`);
    console.log(`API real: ${API_URL}`);
  }

  let previewProc;
  try {
    await waitForUrl(BASE_URL);
  } catch {
    previewProc = startPreview();
    await waitForUrl(BASE_URL);
  }

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on("dialog", (dialog) => dialog.accept());

  if (USE_REAL_API) {
    await login(page);
  } else {
    console.warn("CAPTURE_REAL_API=0: modo mock deshabilitado en esta versión; use API local.");
    await login(page);
  }

  const mobileVps = VIEWPORTS.filter((v) => v.w < 768);
  for (const vp of mobileVps) {
    console.log(`Capturando móvil ${vp.tag}…`);
    await captureMobile(page, vp);
  }

  for (const [vpTag, name] of [
    ["768x1024", "tablet"],
    ["1024x768", "tablet-landscape"],
    ["1366x768", "escritorio"],
  ]) {
    const vp = VIEWPORTS.find((v) => v.tag === vpTag);
    console.log(`Capturando ${vpTag}…`);
    await captureTabletDesktop(page, vp, name);
  }

  await browser.close();
  if (previewProc?.pid) {
    try {
      process.kill(previewProc.pid);
    } catch {
      /* ignore */
    }
  }
  console.log(`Capturas guardadas en ${OUT_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
