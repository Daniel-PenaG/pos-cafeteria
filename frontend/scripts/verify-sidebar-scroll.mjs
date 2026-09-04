/**
 * Verifica scroll vertical del sidebar en web (≥768px) y regresión móvil.
 *
 * Requiere preview + API local (mismo flujo que capture-responsive):
 *   cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
 *   cd frontend && npm run build && npm run preview -- --host 127.0.0.1 --port 4173
 *   npm run verify:sidebar-scroll
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, "../../docs/screenshots/sidebar-scroll");
const BASE_URL = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const API_URL = process.env.API_URL || "http://127.0.0.1:8000";
const LOGIN_USER = process.env.CAPTURE_LOGIN || "admin";
const LOGIN_PASS = process.env.CAPTURE_PASSWORD || "admin123";

const DESKTOP_VIEWPORTS = [
  { w: 768, h: 1024, tag: "768x1024" },
  { w: 1024, h: 768, tag: "1024x768" },
  { w: 1024, h: 600, tag: "1024x600" },
  { w: 1280, h: 600, tag: "1280x600" },
  { w: 1366, h: 768, tag: "1366x768" },
];

const MOBILE_VIEWPORT = { w: 390, h: 844, tag: "390x844" };

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

async function assertApiReal() {
  try {
    const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(10000) });
    if (!res.ok) throw new Error(`API respondió ${res.status}`);
    const body = await res.json();
    if (body?.status !== "ok") {
      throw new Error(`Health check inesperado: ${JSON.stringify(body)}`);
    }
  } catch (err) {
    throw new Error(
      `API real no disponible en ${API_URL}. Inicia: cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000\n${err.message}`
    );
  }
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

async function assertDesktopSidebarScroll(page, vpTag, { capture = false } = {}) {
  const label = `[${vpTag}] desktop sidebar scroll`;

  const nav = page.locator(".sidebar__nav");
  await nav.waitFor({ state: "visible", timeout: 10000 });

  const metrics = await nav.evaluate((el) => ({
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
    overflowY: getComputedStyle(el).overflowY,
    sidebarOverflowY: getComputedStyle(el.closest(".sidebar")).overflowY,
  }));

  if (metrics.scrollHeight <= metrics.clientHeight) {
    throw new Error(
      `${label}: nav no desborda (scrollHeight=${metrics.scrollHeight}, clientHeight=${metrics.clientHeight})`
    );
  }

  if (!/auto|scroll/.test(metrics.overflowY)) {
    throw new Error(`${label}: overflow-y debe ser auto/scroll (actual: ${metrics.overflowY})`);
  }

  if (metrics.sidebarOverflowY !== "hidden") {
    throw new Error(
      `${label}: .sidebar debe tener overflow hidden en desktop (actual: ${metrics.sidebarOverflowY})`
    );
  }

  const brandVisible = await page.locator(".sidebar__brand").isVisible();
  if (!brandVisible) {
    throw new Error(`${label}: encabezado Coffe Song no visible`);
  }

  const dashboardLink = page.locator('.sidebar__nav a[href="/dashboard"]');
  if (!(await dashboardLink.count())) {
    throw new Error(`${label}: enlace Dashboard no encontrado`);
  }

  await nav.evaluate((el) => {
    el.scrollTop = 0;
  });
  await page.waitForTimeout(150);

  if (capture) {
    const dir = path.join(OUT_DIR, vpTag);
    await mkdir(dir, { recursive: true });
    await page.screenshot({ path: path.join(dir, "sidebar-top.png") });
  }

  const scrollResult = await nav.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
    return {
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    };
  });

  if (scrollResult.scrollTop <= 0) {
    throw new Error(`${label}: scrollTop sigue en 0 después de desplazar al fondo`);
  }

  const lastLink = page.locator(".sidebar__nav a.sidebar__link").last();
  const lastBox = await lastLink.boundingBox();
  const navBox = await nav.boundingBox();
  if (!lastBox || !navBox) {
    throw new Error(`${label}: no se pudo medir el último enlace del menú`);
  }

  const lastBottom = lastBox.y + lastBox.height;
  const navBottom = navBox.y + navBox.height;
  if (lastBottom > navBottom + 2) {
    throw new Error(
      `${label}: último enlace queda fuera del área visible (bottom=${lastBottom}, navBottom=${navBottom})`
    );
  }

  if (capture) {
    const dir = path.join(OUT_DIR, vpTag);
    await page.screenshot({ path: path.join(dir, "sidebar-bottom.png") });
  }

  await nav.evaluate((el) => {
    el.scrollTop = 0;
  });
  await page.waitForTimeout(100);

  const pageScroll = await page.evaluate(() => ({
    docScrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  if (pageScroll.docScrollWidth > pageScroll.innerWidth + 1) {
    throw new Error(
      `${label}: scroll horizontal en página (${pageScroll.docScrollWidth} > ${pageScroll.innerWidth})`
    );
  }

  console.log(`OK ${label}`);
}

async function assertMobileSidebarRegression(page) {
  const label = `[${MOBILE_VIEWPORT.tag}] móvil sin regresión`;
  const vp = MOBILE_VIEWPORT;

  await page.setViewportSize({ width: vp.w, height: vp.h });
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await page.waitForSelector(".navbar__menu-btn", { timeout: 10000 });

  const menuBtn = page.locator(".navbar__menu-btn");
  if (await menuBtn.isVisible()) {
    await menuBtn.click({ force: true });
    await page.waitForSelector(".sidebar--open", { timeout: 5000 });
    await page.waitForSelector(".sidebar-overlay", { timeout: 3000 });
  } else {
    throw new Error(`${label}: botón hamburguesa no visible`);
  }

  const navOverflow = await page.locator(".sidebar__nav").evaluate((el) => getComputedStyle(el).overflowY);
  if (/auto|scroll/.test(navOverflow)) {
    throw new Error(`${label}: .sidebar__nav no debe tener scroll propio en móvil (actual: ${navOverflow})`);
  }

  const sidebarOverflow = await page.locator(".sidebar").evaluate((el) => getComputedStyle(el).overflowY);
  if (!/auto|scroll/.test(sidebarOverflow)) {
    throw new Error(`${label}: .sidebar debe permitir scroll en móvil (actual: ${sidebarOverflow})`);
  }

  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const openAfterEscape = await page.locator(".sidebar--open").count();
  if (openAfterEscape > 0) {
    throw new Error(`${label}: sidebar no cerró con Escape`);
  }

  console.log(`OK ${label}`);
}

async function main() {
  await assertApiReal();

  let previewProc;
  try {
    await waitForUrl(BASE_URL);
  } catch {
    previewProc = startPreview();
    await waitForUrl(BASE_URL);
  }

  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("dialog", (dialog) => dialog.accept());

  await login(page);
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await page.waitForSelector(".sidebar__nav", { timeout: 15000 });

  for (const vp of DESKTOP_VIEWPORTS) {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await page.waitForTimeout(200);
    const capture = vp.tag === "1024x600";
    await assertDesktopSidebarScroll(page, vp.tag, { capture });
  }

  await assertMobileSidebarRegression(page);

  await browser.close();
  if (previewProc?.pid) {
    try {
      process.kill(previewProc.pid);
    } catch {
      /* ignore */
    }
  }

  console.log(`Verificación completada. Capturas en ${OUT_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
