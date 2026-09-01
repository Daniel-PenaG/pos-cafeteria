/**
 * Capturas responsive con Playwright — API local obligatoria.
 *
 * Terminal 1: cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
 * Terminal 2:
 *   cd frontend
 *   npm ci && npm run lint
 *   $env:VITE_API_URL="http://127.0.0.1:8000"; npm run build
 *   npm run preview -- --host 127.0.0.1 --port 4173
 * Terminal 3: npm run capture:responsive
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
const LOGIN_USER = process.env.CAPTURE_LOGIN || "admin";
const LOGIN_PASS = process.env.CAPTURE_PASSWORD || "admin123";

const MODAL_BOTTOM_VIEWPORTS = new Set(["320x568", "390x844"]);
const TABLE_ROUTES = new Set(["/reportes", "/usuarios", "/cuentas-cajero"]);

const VIEWPORTS = [
  { w: 320, h: 568, tag: "320x568" },
  { w: 360, h: 800, tag: "360x800" },
  { w: 390, h: 844, tag: "390x844" },
  { w: 412, h: 915, tag: "412x915" },
  { w: 768, h: 1024, tag: "768x1024" },
  { w: 1024, h: 768, tag: "1024x768" },
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

async function assertApiReal() {
  try {
    const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(10000) });
    if (!res.ok) {
      throw new Error(`API respondió ${res.status}`);
    }
    const body = await res.json();
    if (body?.status !== "ok") {
      throw new Error(`Health check inesperado: ${JSON.stringify(body)}`);
    }
  } catch (err) {
    throw new Error(
      `API real no disponible en ${API_URL}. Inicia: cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000\n${err.message}`
    );
  }
  console.log(`API real: ${API_URL}`);
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
  await page.waitForTimeout(400);
}

async function assertNoPageHorizontalScroll(page, label) {
  const metrics = await page.evaluate(() => ({
    docScrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  if (metrics.docScrollWidth > metrics.innerWidth + 1) {
    throw new Error(
      `[${label}] Scroll horizontal en página: documentElement.scrollWidth=${metrics.docScrollWidth} > innerWidth=${metrics.innerWidth}`
    );
  }
}

async function assertTableWraps(page, label) {
  const wraps = page.locator(".table-wrap");
  const count = await wraps.count();
  if (count === 0) return;

  for (let i = 0; i < count; i += 1) {
    const wrap = wraps.nth(i);
    const info = await wrap.evaluate((el) => {
      const table = el.querySelector("table");
      if (!table) return null;
      const style = getComputedStyle(el);
      return {
        wrapClientWidth: el.clientWidth,
        wrapScrollWidth: el.scrollWidth,
        tableScrollWidth: table.scrollWidth,
        overflowX: style.overflowX,
      };
    });
    if (!info) continue;

    const tableNeedsScroll = info.tableScrollWidth > info.wrapClientWidth + 1;
    const wrapCanScroll = info.wrapScrollWidth > info.wrapClientWidth + 1;
    const overflowOk = info.overflowX === "auto" || info.overflowX === "scroll";

    if (tableNeedsScroll && !wrapCanScroll) {
      throw new Error(
        `[${label}] .table-wrap[${i}]: tabla (${info.tableScrollWidth}px) más ancha que contenedor (${info.wrapClientWidth}px) sin scroll`
      );
    }
    if (tableNeedsScroll && !overflowOk) {
      throw new Error(
        `[${label}] .table-wrap[${i}]: overflow-x debe ser auto/scroll (actual: ${info.overflowX})`
      );
    }
  }
}

async function validateRouteLayout(page, routePath, vpTag) {
  const label = `${vpTag} ${routePath}`;
  await assertNoPageHorizontalScroll(page, label);
  if (TABLE_ROUTES.has(routePath)) {
    await assertTableWraps(page, label);
  }
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

async function shot(page, dir, name, { fullPage = true } = {}) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage });
  await page.evaluate(() => window.scrollTo(0, 0));
}

async function capturePromocionesModal(page, dir, vpTag) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(150);

  const nuevaBtn = page.getByRole("button", { name: "Nueva promoción" });
  if (!(await nuevaBtn.count())) {
    throw new Error(`[${vpTag}] Botón "Nueva promoción" no encontrado`);
  }
  await nuevaBtn.click();
  const modal = page.locator(".modal-box");
  await modal.waitFor({ state: "visible", timeout: 10000 });

  await shot(page, dir, "promociones-modal", { fullPage: false });

  const pageScrollBeforeModalScroll = await page.evaluate(() => window.scrollY);

  await page.locator(".modal-box").evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await page.waitForTimeout(350);

  const guardar = page.getByRole("button", { name: /Guardar/i });
  const cancelar = page.getByRole("button", { name: /Cancelar/i });
  if (!(await guardar.count()) || !(await cancelar.count())) {
    throw new Error(`[${vpTag}] Modal promoción: faltan botones Guardar/Cancelar`);
  }

  const vp = page.viewportSize();
  for (const [name, btn] of [
    ["Guardar", guardar.first()],
    ["Cancelar", cancelar.first()],
  ]) {
    const box = await btn.boundingBox();
    if (!box) throw new Error(`[${vpTag}] Botón ${name} sin bounding box`);
    if (box.y + box.height > vp.height) {
      throw new Error(
        `[${vpTag}] Botón ${name} queda detrás de la barra inferior (y=${box.y}, h=${box.height}, viewport=${vp.height})`
      );
    }
  }

  const pageScrollAfter = await page.evaluate(() => window.scrollY);
  if (Math.abs(pageScrollAfter - pageScrollBeforeModalScroll) > 2) {
    throw new Error(
      `[${vpTag}] El scroll del modal desplazó la página (${pageScrollBeforeModalScroll} → ${pageScrollAfter})`
    );
  }

  if (MODAL_BOTTOM_VIEWPORTS.has(vpTag)) {
    await shot(page, dir, "promociones-modal-bottom", { fullPage: false });
  }

  await page.getByRole("button", { name: /Cancelar/i }).first().click();
  await page.waitForTimeout(250);
}

async function captureMobile(page, vp) {
  const dir = path.join(OUT_DIR, vp.tag);
  await mkdir(dir, { recursive: true });
  await page.setViewportSize({ width: vp.w, height: vp.h });
  await ensureLoggedIn(page);

  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await validateRouteLayout(page, "/dashboard", vp.tag);
  await shot(page, dir, "menu-closed");

  await page.locator(".navbar__menu-btn").click({ force: true });
  await page.waitForSelector(".sidebar--open", { timeout: 5000 });
  await page.waitForSelector(".sidebar-overlay", { timeout: 3000 });
  await page.waitForTimeout(300);
  await validateRouteLayout(page, "/dashboard (menú abierto)", vp.tag);
  await shot(page, dir, "menu-open");
  await page.locator(".sidebar__close").click({ force: true });
  await page.waitForTimeout(250);

  await page.goto(`${BASE_URL}/promociones`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await validateRouteLayout(page, "/promociones", vp.tag);
  await shot(page, dir, "promociones");
  await capturePromocionesModal(page, dir, vp.tag);

  await page.goto(`${BASE_URL}/ventas`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  const mesa = page.locator(".mesa-card:not(.mesa-card--add)").first();
  if (await mesa.count()) {
    await mesa.click({ force: true });
    await page.waitForTimeout(900);
    const producto = page.locator(".ventas-producto-item").first();
    if (await producto.count()) {
      await producto.click({ force: true });
      await page.waitForTimeout(700);
    }
  }
  await validateRouteLayout(page, "/ventas", vp.tag);
  await shot(page, dir, "ventas");

  await page.goto(`${BASE_URL}/comandera`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await validateRouteLayout(page, "/comandera", vp.tag);
  await shot(page, dir, "comandera");

  await page.goto(`${BASE_URL}/reportes`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await validateRouteLayout(page, "/reportes", vp.tag);
  await shot(page, dir, "reportes");

  await page.goto(`${BASE_URL}/usuarios`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await validateRouteLayout(page, "/usuarios", vp.tag);
  await shot(page, dir, "usuarios");

  await page.goto(`${BASE_URL}/cuentas-cajero`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await validateRouteLayout(page, "/cuentas-cajero", vp.tag);
  await shot(page, dir, "cuentas-cajero");
}

async function captureTabletDesktop(page, vp, name) {
  const dir = path.join(OUT_DIR, vp.tag);
  await mkdir(dir, { recursive: true });
  await page.setViewportSize({ width: vp.w, height: vp.h });
  await ensureLoggedIn(page);

  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: false });
  await validateRouteLayout(page, "/dashboard", vp.tag);
  await shot(page, dir, name);

  await page.goto(`${BASE_URL}/reportes`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: false });
  await validateRouteLayout(page, "/reportes", vp.tag);
  await shot(page, dir, `${name}-reportes`);
}

async function main() {
  if (process.env.CAPTURE_REAL_API === "0") {
    throw new Error("CAPTURE_REAL_API=0 no permitido. Este script exige API local real.");
  }

  await assertApiReal();

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

  await login(page);

  for (const vp of VIEWPORTS.filter((v) => v.w < 768)) {
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
