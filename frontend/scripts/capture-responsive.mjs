/**
 * Genera capturas responsive con Playwright.
 * Uso: npm run build && npm run preview & node scripts/capture-responsive.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, "../../docs/screenshots/responsive");
const BASE_URL = process.env.PREVIEW_URL || "http://127.0.0.1:4173";

const VIEWPORTS = [
  { w: 320, h: 568, tag: "320x568" },
  { w: 360, h: 800, tag: "360x800" },
  { w: 390, h: 844, tag: "390x844" },
  { w: 412, h: 915, tag: "412x915" },
  { w: 768, h: 1024, tag: "768x1024" },
  { w: 1024, h: 768, tag: "1024x768" },
  { w: 1366, h: 768, tag: "1366x768" },
];

const AUTH = {
  token: "screenshot-token",
  user: {
    id_usuario: 1,
    nombre: "Admin Demo",
    rol: "ADMIN",
    modulos: null,
  },
};

async function waitForPreview(url, timeoutMs = 60000) {
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
  throw new Error(`Preview no disponible en ${url}`);
}

function startPreview() {
  return spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", "4173"], {
    cwd: path.resolve(__dirname, ".."),
    shell: true,
    stdio: "ignore",
    detached: process.platform !== "win32",
  });
}

function mockApiBody(url) {
  if (url.includes("/auth/me")) return AUTH.user;
  if (url.includes("resumen-dashboard")) {
    return {
      hoy: "2026-08-31",
      total_hoy: 0,
      total_gastos_hoy: 0,
      capital_neto_hoy: 0,
      num_ventas_hoy: 0,
      comanda_promedio_texto: "0s",
      total_general: 0,
      top_productos: [],
      ventas_recientes: [],
      gastos_hoy: [],
    };
  }
  if (url.includes("configuracion")) {
    return { margen_ganancia: 30, gastos_fijos: 0 };
  }
  if (url.includes("promociones/resumen") || url.includes("promociones-resumen")) {
    return { total_descuento: 0, total_ventas_con_promo: 0 };
  }
  if (url.includes("promociones")) return [];
  if (url.includes("productos")) {
    return [
      { id_producto: 1, nombre: "Latte", precio: 45, id_categoria: 1, activo: true },
      { id_producto: 2, nombre: "Croissant", precio: 35, id_categoria: 2, activo: true },
    ];
  }
  if (url.includes("categorias")) {
    return [
      { id_categoria: 1, nombre: "Bebidas", activa: true },
      { id_categoria: 2, nombre: "Pan", activa: true },
    ];
  }
  if (url.includes("usuarios")) return [];
  if (url.includes("/pedidos/mesas")) return { mesas: [1, 2, 3, 4] };
  if (url.includes("/pedidos/activos")) return [];
  if (url.includes("/pedidos/mesa/")) {
    return {
      id_pedido: 1,
      numero_mesa: 1,
      lineas: [
        {
          id_detalle: 1,
          nombre_producto: "Latte",
          cantidad: 2,
          precio_unitario: 45,
          en_comanda: true,
        },
        {
          id_detalle: 2,
          nombre_producto: "Croissant",
          cantidad: 1,
          precio_unitario: 35,
          en_comanda: true,
        },
      ],
      subtotal_normal: 125,
      descuento_promociones: 0,
      resumen_promociones: [],
    };
  }
  if (url.includes("comandera")) return [];
  if (url.includes("extras-venta/tipos")) return {};
  if (url.includes("extras-venta")) return [];
  if (url.includes("/ventas/extras")) return [];
  if (url.includes("ventas")) return [];
  if (url.includes("reportes")) {
    return {
      productos: [],
      desglose_dias: [],
      venta_total: 0,
      numero_tickets: 0,
      ticket_promedio: 0,
      unidades_vendidas: 0,
    };
  }
  if (url.includes("cuentas")) return { cajeros: [] };
  return {};
}

async function setupApiMocks(context) {
  await context.route("**/*", (route) => {
    const url = route.request().url();
    const isApi =
      url.includes("onrender.com") ||
      url.includes("127.0.0.1:8000") ||
      url.includes("localhost:8000");

    if (!isApi) return route.continue();

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockApiBody(url)),
    });
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
  await page.waitForTimeout(500);
}

async function injectAuth(page) {
  await page.addInitScript((auth) => {
    localStorage.setItem("pos_cafeteria_auth", JSON.stringify(auth));
  }, AUTH);
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

  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await shot(page, dir, "menu-closed");

  await page.locator(".navbar__menu-btn").click({ force: true });
  await page.waitForTimeout(400);
  await shot(page, dir, "menu-open");
  await page.locator(".sidebar__close").click({ force: true });
  await page.waitForTimeout(200);

  await page.goto(`${BASE_URL}/promociones`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await shot(page, dir, "promociones");

  await page.getByRole("button", { name: "Nueva promoción" }).click({ timeout: 10000 }).catch(async () => {
    await page.locator("button", { hasText: "Nueva promoción" }).click();
  });
  await page.waitForTimeout(300);
  await shot(page, dir, "promociones-modal");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);

  await page.goto(`${BASE_URL}/ventas`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: true });
  await page.locator(".mesa-card").first().click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(800);
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
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: false });
  await shot(page, dir, name);
  await page.goto(`${BASE_URL}/reportes`, { waitUntil: "load" });
  await waitAppReady(page, { mobile: false });
  await shot(page, dir, `${name}-reportes`);
}

async function main() {
  let previewProc;
  try {
    await fetch(BASE_URL);
  } catch {
    previewProc = startPreview();
    await waitForPreview(BASE_URL);
  }

  const browser = await chromium.launch();
  const context = await browser.newContext();
  await setupApiMocks(context);
  const page = await context.newPage();
  page.on("dialog", (dialog) => dialog.accept());
  await injectAuth(page);

  const mobileVps = VIEWPORTS.filter((v) => v.w < 768);
  for (const vp of mobileVps) {
    await captureMobile(page, vp);
  }

  await captureTabletDesktop(page, VIEWPORTS.find((v) => v.tag === "768x1024"), "tablet");
  await captureTabletDesktop(page, VIEWPORTS.find((v) => v.tag === "1024x768"), "tablet-landscape");
  await captureTabletDesktop(page, VIEWPORTS.find((v) => v.tag === "1366x768"), "escritorio");

  await browser.close();
  if (previewProc) {
    process.kill(-previewProc.pid);
  }
  console.log(`Capturas guardadas en ${OUT_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
