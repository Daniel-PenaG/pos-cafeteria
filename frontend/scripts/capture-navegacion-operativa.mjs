/**
 * 9 escenarios × 3 viewports — API real, seed E2E (run-perf-e2e.ps1).
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  E2E_PRODUCT_SIN_PROMO,
  expandirCatalogo,
  esperarAgregarHabilitado,
  esperarFormularioProducto,
  isContextoResponse,
  isPostLineaResponse,
  clickSidebarNav,
} from "./perf-e2e-shared.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, "../../docs/screenshots/navegacion-operativa");
const REMOTE_API = "https://pos-cafeteria-api.onrender.com";
const VIEWPORTS = [
  { w: 390, h: 844, tag: "390x844" },
  { w: 768, h: 1024, tag: "768x1024" },
  { w: 1366, h: 768, tag: "1366x768" },
];

function requireEnv(n) {
  const v = (process.env[n] || "").trim();
  if (!v) throw new Error(`Falta ${n}`);
  return v;
}

function assertLocal(label, raw) {
  const u = new URL(raw);
  if (!["127.0.0.1", "localhost", "::1"].includes((u.hostname || "").toLowerCase())) {
    throw new Error(`${label} debe ser localhost`);
  }
  return raw.replace(/\/$/, "");
}

async function api(API, method, pathName, token, body) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${pathName}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const raw = await res.text();
  let parsed = {};
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = {};
    }
  }
  return { status: res.status, body: parsed };
}

async function installLocalApiRoute(context, apiTarget) {
  const target = apiTarget.replace(/\/$/, "");
  await context.route("**/*", (route) => {
    const url = route.request().url();
    if (url.includes("onrender.com") || url.startsWith(REMOTE_API)) {
      return route.continue({ url: url.replace(REMOTE_API, target) });
    }
    return route.continue();
  });
}

async function loginPage(page, base, user, pass) {
  await page.goto(`${base}/login`, { waitUntil: "domcontentloaded" });
  await page.fill("#user", user);
  await page.fill("#pass", pass);
  await page.getByRole("button", { name: /Entrar al sistema/i }).click();
  await page.waitForURL((u) => !u.pathname.endsWith("/login"), { timeout: 60000 });
}

async function assertUi(page, label) {
  const m = await page.evaluate(() => ({
    horiz: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  if (m.horiz > 8) throw new Error(`${label}: scroll horizontal`);
}

async function shot(page, subdir, name) {
  await assertUi(page, `${subdir}/${name}`);
  const dir = path.join(OUT_DIR, subdir);
  await mkdir(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true });
}

async function abrirCaja(API, token) {
  const ses = await api(API, "GET", "/caja/sesion-actual", token);
  if (ses.status === 200 && ses.body?.abierta) return;
  await api(API, "POST", "/caja/apertura", token, { efectivo_inicial: 500, operation_id: crypto.randomUUID() });
}

async function agregarLineaUi(page) {
  await expandirCatalogo(page, E2E_PRODUCT_SIN_PROMO);
  const postLinea = page.waitForResponse(isPostLineaResponse, { timeout: 90000 });
  await page.locator(".ventas-producto-item").first().click();
  await page.waitForResponse(isContextoResponse, { timeout: 60000 });
  await esperarFormularioProducto(page);
  await esperarAgregarHabilitado(page);
  await page.getByRole("button", { name: /Agregar al pedido/i }).click();
  await postLinea;
  await page.waitForSelector('[data-nav-pedido="ready"]', { timeout: 30000 });
}

async function prepPedidoCobro(API, token, uid, mesa, idProducto, precio) {
  await api(API, "POST", `/pedidos/mesa/${mesa}/lineas?id_usuario=${uid}`, token, {
    id_producto: idProducto,
    cantidad: 1,
    precio_unitario: precio,
    extras: [],
    operation_id: crypto.randomUUID(),
  });
  const ped = await api(API, "GET", `/pedidos/mesa/${mesa}?id_usuario=${uid}`, token);
  await api(API, "POST", `/pedidos/${ped.body.id_pedido}/confirmar-comanda`, token);
  const pend = await api(API, "GET", "/comandera/pendientes", token);
  const linea = (Array.isArray(pend.body) ? pend.body : []).find((l) => l.numero_mesa === mesa);
  if (linea?.id_detalle_pedido) {
    await api(API, "POST", `/comandera/lineas/${linea.id_detalle_pedido}/listo?id_usuario=${uid}`, token, {
      cantidad: 1,
      operation_id: crypto.randomUUID(),
    });
  }
  return ped.body;
}

async function capturarResumenesCobro(page, base, API, token, uid, vpTag, vpIdx, idProducto, precio) {
  const mesaEf = 24 + vpIdx;
  const mesaPts = 27 + vpIdx;
  const mesaInv = 30 + vpIdx;

  await prepPedidoCobro(API, token, uid, mesaEf, idProducto, precio);
  await page.goto(`${base}/ventas?mesa=${mesaEf}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".cart-item", { timeout: 20000 });
  await page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i }).click();
  await page.waitForSelector(".modal-box--cobro", { timeout: 15000 });
  const monto = page.locator("#monto-recibido");
  if (await monto.count()) {
    const t = await page.locator(".modal-box--cobro .cart-total").first().innerText();
    await monto.fill((t.match(/[\d.]+/) || ["50"])[0]);
  }
  await page.getByRole("button", { name: /Cobrar sin cliente/i }).click();
  await page.waitForSelector('[data-nav-cobro-resumen="visible"]', { timeout: 30000 });
  await shot(page, vpTag, "05-resumen-cobro-efectivo");
  await page.getByRole("button", { name: /^Continuar$/i }).click();
  await page.waitForFunction(
    () => !document.querySelector('[data-nav-cobro-resumen="visible"]'),
    null,
    { timeout: 10000 }
  ).catch(() => {});

  await prepPedidoCobro(API, token, uid, mesaPts, idProducto, precio);
  const clientes = await api(API, "GET", "/clientes?activo=true", token);
  const lista = Array.isArray(clientes.body) ? clientes.body : clientes.body?.items || [];
  const cliente = lista.find((c) => c.codigo_fidelidad === "CAP-E2E-01") || lista[0];
  if (cliente?.id_cliente) {
    const ped = (await api(API, "GET", `/pedidos/mesa/${mesaPts}?id_usuario=${uid}`, token)).body;
    await api(API, "PUT", `/pedidos/${ped.id_pedido}/cliente`, token, { id_cliente: cliente.id_cliente });
  }
  await page.goto(`${base}/ventas?mesa=${mesaPts}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".cart-item", { timeout: 20000 });
  await page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i }).click();
  await page.waitForSelector(".modal-box--cobro", { timeout: 15000 });
  await page.waitForSelector(".modal-box--cobro .badge", { timeout: 20000 });
  await page.locator("#puntos-canje").fill("50");
  const montoMix = page.locator("#monto-recibido");
  if (await montoMix.count()) {
    await page.waitForTimeout(400);
    const hintRest = page.locator(".modal-box--cobro .hint", { hasText: /Resta \$/i }).first();
    const hintRaw = await hintRest.innerText().catch(() => "");
    const restMatch = hintRaw.match(/Resta\s*\$?\s*([\d]+(?:\.\d{1,2})?)/i);
    const minAttr = await montoMix.getAttribute("placeholder").catch(() => "");
    const minMatch = (minAttr || "").match(/([\d]+(?:\.\d{1,2})?)/);
    const totalTxt = await page.locator(".modal-box--cobro .cart-total").first().innerText();
    const totalMatch = totalTxt.match(/([\d]+(?:\.\d{1,2})?)/);
    const montoVal = restMatch?.[1] || minMatch?.[1] || totalMatch?.[1] || "30";
    await montoMix.fill(montoVal);
  }
  await page.getByRole("button", { name: /Cobrar con Cliente Captura E2E/i }).click({ timeout: 60000 });
  await page
    .waitForSelector('[data-nav-cobro-resumen="visible"], .modal-box--cobro-exito', { timeout: 45000 })
    .catch(() => {});
  await shot(page, vpTag, "06-resumen-cobro-mixto-puntos");
  await page.getByRole("button", { name: /^Continuar$/i }).click().catch(() => {});

  await prepPedidoCobro(API, token, uid, mesaInv, idProducto, precio);
  await page.goto(`${base}/ventas?mesa=${mesaInv}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".cart-item", { timeout: 20000 });
  await page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i }).click();
  await page.waitForSelector(".modal-box--cobro", { timeout: 15000 });
  const montoInv = page.locator("#monto-recibido");
  if (await montoInv.count()) {
    const t = await page.locator(".modal-box--cobro .cart-total").first().innerText();
    const m = t.match(/([\d]+(?:\.\d{1,2})?)/);
    await montoInv.fill(m?.[1] || "35");
  }
  await page.getByRole("button", { name: /Cobrar sin cliente/i }).click();
  await page.waitForSelector('[data-nav-cobro-resumen="visible"]', { timeout: 30000 });
  await shot(page, vpTag, "07-advertencias-inventario-resumen");
  await page.getByRole("button", { name: /^Continuar$/i }).click();
}

async function runViewport(page, base, API, token, uid, vpTag, vpIdx, idProducto, precio) {
  const mesaNav = 15 + vpIdx * 3;
  const mesaSwr = mesaNav + 1;
  const mesaToast = mesaNav + 2;
  const mesaCancel = 36 + vpIdx;
  const mesa409 = 33 + vpIdx;

  await page.goto(`${base}/ventas?mesa=${mesaNav}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-nav-shell="ventas"]', { timeout: 60000 });
  await agregarLineaUi(page);
  await clickSidebarNav(page, /Comandera/i);
  await page.waitForSelector('[data-nav-shell="comandera"]', { timeout: 60000 });
  await clickSidebarNav(page, /Ventas/i);
  await page.waitForSelector('[data-nav-catalog="ready"]', { timeout: 60000 });
  await shot(page, vpTag, "01-regreso-comandera-ventas");

  await page.evaluate(() => window.__posE2e?.pulseCatalogRevalidatingBanner?.());
  const rev = page.locator('[data-nav-revalidating="1"]');
  await rev.waitFor({ state: "visible", timeout: 10000 });
  await shot(page, vpTag, "02-swr-actualizando");
  await page.evaluate(() => {
    document.querySelector("[data-nav-revalidating]")?.remove();
  });

  await page.goto(`${base}/ventas?mesa=${mesaToast}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-nav-shell="ventas"]', { timeout: 60000 });
  await agregarLineaUi(page);
  await page.waitForFunction(
    () => {
      const btn = [...document.querySelectorAll("button")].find((b) =>
        (b.textContent || "").includes("Confirmar pedido")
      );
      return btn && !btn.disabled;
    },
    null,
    { timeout: 60000 }
  );
  await page.getByRole("button", { name: /Confirmar pedido/i }).click();
  await page.waitForSelector(".toast--success", { timeout: 15000 });
  await shot(page, vpTag, "03-toast-comanda-confirmada");

  await page.goto(`${base}/ventas?mesa=${mesaCancel}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-nav-shell="ventas"]', { timeout: 60000 });
  await agregarLineaUi(page);
  await page.waitForFunction(
    () => {
      const btn = [...document.querySelectorAll("button")].find((b) =>
        (b.textContent || "").includes("Confirmar pedido")
      );
      return btn && !btn.disabled;
    },
    null,
    { timeout: 60000 }
  );
  await page.getByRole("button", { name: /Confirmar pedido/i }).click();
  await page.waitForSelector(".toast--success", { timeout: 15000 });
  const delBtn = page
    .locator(".cart-item")
    .first()
    .locator('button[aria-label*="Cancelar producto"]')
    .first();
  await delBtn.waitFor({ state: "visible", timeout: 15000 });
  await delBtn.click();
  await page.waitForSelector(".modal-box", { timeout: 10000 });
  await shot(page, vpTag, "04-modal-cancelacion-linea");
  await page.keyboard.press("Escape");

  await capturarResumenesCobro(page, base, API, token, uid, vpTag, vpIdx, idProducto, precio);

  await prepPedidoCobro(API, token, uid, mesa409, idProducto, precio);
  await page.goto(`${base}/ventas?mesa=${mesa409}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".cart-item", { timeout: 20000 });
  await page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i }).click();
  await page.waitForSelector(".modal-box--cobro", { timeout: 15000 });
  const monto409 = page.locator("#monto-recibido");
  if (await monto409.count()) {
    const t = await page.locator(".modal-box--cobro .cart-total").first().innerText();
    const m = t.match(/([\d]+(?:\.\d{1,2})?)/);
    await monto409.fill(m?.[1] || "35");
  }
  const linePromise = api(API, "POST", `/pedidos/mesa/${mesa409}/lineas?id_usuario=${uid}`, token, {
    id_producto: idProducto,
    cantidad: 1,
    precio_unitario: precio,
    extras: [],
    operation_id: crypto.randomUUID(),
  });
  const clickPromise = page.getByRole("button", { name: /Cobrar sin cliente/i }).click();
  await Promise.all([linePromise, clickPromise]);
  const recalcBtn = page.getByRole("button", { name: /Cobrar con el total actualizado/i });
  const gotRecalc = await recalcBtn.waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
  const pedDesp = (await api(API, "GET", `/pedidos/mesa/${mesa409}?id_usuario=${uid}`, token)).body;
  if (!gotRecalc && pedDesp?.estado === "COBRADO") {
    throw new Error("409: cobró sin modal de recálculo");
  }
  await shot(page, vpTag, "08-409-recalculo-pedido-abierto");
  if (gotRecalc) {
    await page.getByRole("button", { name: /^Cancelar$/i }).click().catch(() => {});
  } else {
    await page.keyboard.press("Escape").catch(() => {});
  }

  await page.goto(`${base}/ventas?mesa=${mesaNav}`, { waitUntil: "domcontentloaded" });
  await page.evaluate(() => {
    const box = document.querySelector(".modal-box");
    if (box) box.remove();
  });
  await page.evaluate(() => {
    const ev = new CustomEvent("pos:forbidden", { detail: "Operación no permitida (demo API)" });
    window.dispatchEvent(ev);
  });
  await page.waitForSelector(".toast--error", { timeout: 8000 }).catch(() => {});
  await shot(page, vpTag, "09-error-toast-no-bloqueante");
}

async function main() {
  const BASE = assertLocal("PREVIEW_URL", requireEnv("PREVIEW_URL"));
  const API = assertLocal("API_URL", requireEnv("API_URL"));
  const user = requireEnv("CAPTURE_LOGIN");
  const pass = requireEnv("CAPTURE_PASSWORD");

  const login = await api(API, "POST", "/auth/login", null, { usuario_login: user, password: pass });
  const token = login.body.access_token;
  const uid = login.body.user?.id_usuario ?? 1;
  await abrirCaja(API, token);

  const prods = await api(API, "GET", "/catalogo/productos", token);
  const prod = (Array.isArray(prods.body) ? prods.body : []).find((p) => p.nombre === E2E_PRODUCT_SIN_PROMO);
  if (!prod) throw new Error("E2E Sin Promo no en catálogo");
  const ctx = await api(API, "GET", `/ventas/productos/${prod.id_producto}/contexto`, token);
  const precio = ctx.body?.calculo_inicial?.precio_unitario ?? prod.precio_venta ?? 50;

  const resumenOnly = process.env.E2E_CAPTURE_RESUMEN_ONLY === "1";
  const browser = await chromium.launch();
  for (let i = 0; i < VIEWPORTS.length; i++) {
    const vp = VIEWPORTS[i];
    const context = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
    await installLocalApiRoute(context, API);
    const page = await context.newPage();
    await loginPage(page, BASE, user, pass);
    if (resumenOnly) {
      await capturarResumenesCobro(page, BASE, API, token, uid, vp.tag, i, prod.id_producto, precio);
    } else {
      await runViewport(page, BASE, API, token, uid, vp.tag, i, prod.id_producto, precio);
    }
    await context.close();
  }
  await browser.close();
  console.log(`Capturas → ${OUT_DIR}`);
}

main().catch((e) => {
  console.error(e.stack || e.message);
  process.exit(1);
});
