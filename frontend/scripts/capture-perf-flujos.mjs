/**
 * Capturas flujos operativos (rendimiento) — 390, 768, 1366.
 * Requiere CAPTURE_LOGIN / CAPTURE_PASSWORD y API + preview locales.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  appendInventarioAMensajeCobro,
  buildResumenInventarioCobro,
} from "../src/utils/cobroAdvertencias.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, "../../docs/screenshots/rendimiento-flujos");

function requireEnv(name) {
  const value = (process.env[name] || "").trim();
  if (!value) throw new Error(`Falta ${name} en el entorno.`);
  return value;
}

function assertLocalUrl(label, raw) {
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`${label} no es una URL válida`);
  }
  const host = (parsed.hostname || "").toLowerCase();
  if (!["127.0.0.1", "localhost", "::1"].includes(host)) {
    throw new Error(`${label} debe ser localhost`);
  }
  return raw.replace(/\/$/, "");
}

const BASE = assertLocalUrl("PREVIEW_URL", process.env.PREVIEW_URL || "http://127.0.0.1:4173");
const API = assertLocalUrl("API_URL", process.env.API_URL || "http://127.0.0.1:8000");
const LOGIN_USER = requireEnv("CAPTURE_LOGIN");
const LOGIN_PASS = requireEnv("CAPTURE_PASSWORD");
const opId = () => crypto.randomUUID();

const REMOTE_API = "https://pos-cafeteria-api.onrender.com";

async function installLocalApiRoute(context, apiTarget) {
  const target = apiTarget.replace(/\/$/, "");
  await context.route("**/*", (route) => {
    const url = route.request().url();
    if (url.includes("onrender.com") || url.startsWith(REMOTE_API)) {
      const next = url.replace(REMOTE_API, target);
      return route.continue({ url: next });
    }
    return route.continue();
  });
}

const VIEWPORTS = [
  { w: 390, h: 844, tag: "390x844" },
  { w: 768, h: 1024, tag: "768x1024" },
  { w: 1366, h: 768, tag: "1366x768" },
];

async function api(method, pathName, token, body) {
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
      parsed = { detail: "respuesta no JSON" };
    }
  }
  return { status: res.status, body: parsed };
}

async function loginApi() {
  const { status, body } = await api("POST", "/auth/login", null, {
    usuario_login: LOGIN_USER,
    password: LOGIN_PASS,
  });
  if (status !== 200 || !body.access_token) {
    throw new Error(`Login de captura falló (${status}).`);
  }
  return body;
}

async function loginPage(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.fill("#user", LOGIN_USER);
  await page.fill("#pass", LOGIN_PASS);
  await page.getByRole("button", { name: /Entrar al sistema/i }).click();
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 60000 });
  await page.waitForSelector(".app-shell", { timeout: 90000 });
}

async function assertUiQuality(page, label) {
  const metrics = await page.evaluate(() => {
    const doc = document.documentElement;
    const horiz = doc.scrollWidth - doc.clientWidth;
    const alertLen = (window.__lastAlertLen || 0);
    const overlay = document.querySelector(".modal-overlay:not([data-capture-inv])");
    const viewportH = window.innerHeight;
    let overlayBlocks = false;
    if (overlay && !overlay.querySelector(".modal-box")) {
      overlayBlocks = overlay.getBoundingClientRect().height > viewportH * 0.92;
    }
    return { horiz, alertLen, overlayBlocks };
  });
  if (metrics.horiz > 8) {
    throw new Error(`${label}: scroll horizontal (${metrics.horiz}px)`);
  }
  if (metrics.alertLen > 1200) {
    throw new Error(`${label}: alerta demasiado larga (${metrics.alertLen} chars)`);
  }
  if (metrics.overlayBlocks) {
    throw new Error(`${label}: overlay bloquea casi toda la pantalla`);
  }
}

async function shot(page, subdir, name) {
  await assertUiQuality(page, `${subdir}/${name}`);
  const dir = path.join(OUT_DIR, subdir);
  await mkdir(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true });
}

async function dismissDialogs(page) {
  page.on("dialog", async (d) => {
    await page.evaluate((len) => {
      window.__lastAlertLen = len;
    }, (d.message() || "").length);
    await d.accept().catch(() => {});
  });
}

async function abrirCaja(token) {
  const ses = await api("GET", "/caja/sesion-actual", token);
  if (ses.status === 200 && ses.body?.abierta) return;
  await api("POST", "/caja/apertura", token, {
    efectivo_inicial: 500,
    operation_id: opId(),
  });
}

async function expandirCatalogo(page, term = "Latte") {
  const search = page.getByPlaceholder(/Buscar producto/i);
  await search.waitFor({ state: "visible", timeout: 30000 });
  await search.fill(term);
  await page.waitForSelector(".ventas-producto-item", { timeout: 60000 });
}

async function clickCobrar(page) {
  const btn = page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i });
  await btn.scrollIntoViewIfNeeded();
  await btn.click({ timeout: 60000 });
}

async function agregarLineaApi(token, uid, mesa, idProducto, extras = []) {
  const ctx = await api("GET", `/ventas/productos/${idProducto}/contexto`, token);
  const precio = ctx.body?.calculo_inicial?.precio_unitario ?? 0;
  await api("POST", `/pedidos/mesa/${mesa}/lineas?id_usuario=${uid}`, token, {
    id_producto: idProducto,
    cantidad: 1,
    precio_unitario: precio,
    extras,
    operation_id: opId(),
  });
}

async function runFlujosViewport(page, session, token, uid, vpTag) {
  await dismissDialogs(page);
  await loginPage(page);

  const prods = await api("GET", "/catalogo/productos", token);
  if (!Array.isArray(prods.body) || prods.body.length === 0) {
    throw new Error(`Catálogo vacío en API (${prods.status})`);
  }

  // 1 — Producto sencillo
  const catalogWait = page.waitForResponse(
    (r) => r.url().includes("/catalogo/productos") && r.status() === 200,
    { timeout: 60000 }
  );
  await page.goto(`${BASE}/ventas?mesa=1`, { waitUntil: "domcontentloaded" });
  await catalogWait;
  await page.waitForSelector(".ventas-mesas-bar__actual", { timeout: 30000 });
  await expandirCatalogo(page);
  const prodBtn = page.locator(".ventas-producto-item").first();
  await prodBtn.scrollIntoViewIfNeeded();
  const postLinea = page.waitForResponse(
    (r) =>
      r.url().includes("/pedidos/mesa/") &&
      r.url().includes("/lineas") &&
      r.request().method() === "POST" &&
      r.status() >= 200 &&
      r.status() < 300,
    { timeout: 90000 }
  );
  const ctxFirst = page.waitForResponse(
    (r) => r.url().includes("/contexto") && r.status() === 200,
    { timeout: 60000 }
  );
  await prodBtn.click();
  await ctxFirst;
  const promoHeading = page.getByRole("heading", { name: /Aplicar promoción/i });
  let hasPromo = false;
  try {
    await promoHeading.waitFor({ state: "visible", timeout: 20000 });
    hasPromo = true;
  } catch {
    hasPromo = false;
  }
  if (hasPromo) {
    await page.getByRole("button", { name: /No, precio normal/i }).click();
    await page.waitForResponse(
      (r) =>
        r.url().includes("/promociones/calcular") &&
        r.request().method() === "POST" &&
        r.status() === 200,
      { timeout: 60000 }
    );
  }
  const agregarBtn = page.getByRole("button", { name: /Agregar al pedido/i });
  if (await agregarBtn.isVisible().catch(() => false)) {
    await page.waitForFunction(
      () => {
        const btn = [...document.querySelectorAll("button")].find((b) =>
          (b.textContent || "").includes("Agregar al pedido")
        );
        return btn && !btn.disabled;
      },
      null,
      { timeout: 45000 }
    );
    await agregarBtn.click();
  }
  const lineRes = await postLinea;
  if (!lineRes.ok()) {
    throw new Error(`Agregar línea falló HTTP ${lineRes.status()}`);
  }
  await page.waitForSelector(".cart-item", { timeout: 15000 });
  await shot(page, vpTag, "01-producto-sencillo");

  // 2 — Producto con extras (modal)
  await page.goto(`${BASE}/ventas?mesa=2`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1000);
  await expandirCatalogo(page);
  const personalizar = page.getByRole("button", { name: /Personalizar/i }).first();
  if (await personalizar.count()) {
    await personalizar.click();
    await page.waitForSelector(".modal-box", { timeout: 15000 });
    const extraChk = page.locator('.modal-box input[type="checkbox"]').first();
    if (await extraChk.count()) await extraChk.check();
    await shot(page, vpTag, "02-producto-con-extras");
    await page.keyboard.press("Escape");
  } else {
    await shot(page, vpTag, "02-producto-con-extras");
  }

  // 3 — Confirmar pedido
  await page.goto(`${BASE}/ventas?mesa=3`);
  await page.waitForTimeout(800);
  await agregarLineaApi(token, uid, 3, 1);
  await page.reload();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: /Confirmar pedido/i }).waitFor({ timeout: 15000 });
  await shot(page, vpTag, "03-confirmar-pedido");

  // 4–5 — Comandera antes / después listo
  await agregarLineaApi(token, uid, 4, 1);
  const ped4 = await api("GET", `/pedidos/mesa/4?id_usuario=${uid}`, token);
  await api("POST", `/pedidos/${ped4.body.id_pedido}/confirmar-comanda`, token);
  await page.goto(`${BASE}/comandera`);
  await page.waitForTimeout(1500);
  await shot(page, vpTag, "04-comandera-antes-listo");
  const listoBtn = page.getByRole("button", { name: /1 listo/i }).first();
  if (await listoBtn.count()) {
    await listoBtn.click();
    await page.waitForTimeout(400);
    await page.waitForFunction(
      () => !document.body.textContent.includes("Marcando…"),
      null,
      { timeout: 15000 }
    ).catch(() => {});
    const updating = await page.getByText(/Actualizando…/i).count();
    if (updating > 0) {
      throw new Error(`${vpTag}: Comandera muestra Actualizando… tras marcar listo`);
    }
  }
  await shot(page, vpTag, "05-comandera-despues-listo");

  // 6 — Cobro (modal)
  await page.goto(`${BASE}/ventas?mesa=5`);
  await page.waitForTimeout(800);
  await agregarLineaApi(token, uid, 5, 1);
  const ped5 = await api("GET", `/pedidos/mesa/5?id_usuario=${uid}`, token);
  await api("POST", `/pedidos/${ped5.body.id_pedido}/confirmar-comanda`, token);
  await page.reload();
  await page.waitForTimeout(1000);
  await clickCobrar(page);
  await page.waitForSelector(".modal-box--cobro", { timeout: 15000 });
  await shot(page, vpTag, "06-cobro");
  await page.locator(".modal-box--cobro .btn--secondary").first().click().catch(() => {});

  // 7 — Advertencia inventario resumida (representación visual del mensaje post-cobro)
  const avisosDemo = [
    { nombre: "Leche", requerido: 1200, disponible: 50 },
    { nombre: "Café", requerido: 800, disponible: 10 },
    { nombre: "Azúcar", requerido: 200, disponible: 0 },
    { nombre: "Vaso", requerido: 50, disponible: 5 },
  ];
  const msgInv = appendInventarioAMensajeCobro("Cuenta cerrada.", avisosDemo);
  const resumen = buildResumenInventarioCobro(avisosDemo);
  await page.evaluate(
    ({ msg, resumenText, esResumido }) => {
      const box = document.createElement("div");
      box.className = "modal-overlay";
      box.setAttribute("data-capture-inv", "1");
      box.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;z-index:9999";
      const inner = document.createElement("div");
      inner.className = "modal-box";
      inner.style.cssText = "max-width:420px;white-space:pre-wrap;font-family:inherit;padding:1.25rem";
      inner.textContent = msg;
      box.appendChild(inner);
      document.body.appendChild(box);
      if (esResumido) {
        const hint = document.createElement("p");
        hint.className = "hint";
        hint.textContent = `Resumen (${resumenText.split("\\n").length} líneas visibles)`;
        inner.prepend(hint);
      }
    },
    { msg: msgInv, resumenText: resumen.texto, esResumido: resumen.esResumido }
  );
  await shot(page, vpTag, "07-advertencia-inventario");
  await page.evaluate(() =>
    document.querySelector(".modal-overlay[data-capture-inv]")?.remove()
  );

  // 8 — Para llevar
  await page.goto(`${BASE}/ventas-para-llevar`);
  await page.waitForTimeout(1500);
  await shot(page, vpTag, "08-para-llevar");

  // 9 — Puntos (modal cobro con cliente)
  await page.goto(`${BASE}/ventas?mesa=6`);
  await page.waitForTimeout(800);
  await agregarLineaApi(token, uid, 6, 1);
  const ped6Prep = await api("GET", `/pedidos/mesa/6?id_usuario=${uid}`, token);
  await api("POST", `/pedidos/${ped6Prep.body.id_pedido}/confirmar-comanda`, token);
  await page.reload();
  await page.waitForTimeout(1000);
  await clickCobrar(page);
  await page.waitForSelector(".modal-box--cobro", { timeout: 15000 });
  const clientes = await api("GET", "/clientes?activo=true", token);
  const lista = Array.isArray(clientes.body) ? clientes.body : clientes.body?.items || [];
  const cliente = lista.find((c) => c.puntos_saldo > 0) || lista[0];
  if (cliente?.id_cliente) {
    const ped6 = (await api("GET", `/pedidos/mesa/6?id_usuario=${uid}`, token)).body;
    await api("PUT", `/pedidos/${ped6.id_pedido}/cliente`, token, {
      id_cliente: cliente.id_cliente,
    });
    await page.reload();
    await page.waitForTimeout(800);
    await clickCobrar(page);
    await page.waitForSelector("h3", { hasText: "Cliente frecuente" });
    await page.waitForSelector(".cliente-seleccionado", { timeout: 10000 });
  }
  await shot(page, vpTag, "09-puntos");
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const health = await fetch(`${API}/health`);
  if (!health.ok) throw new Error(`API no disponible en ${API}`);
  const session = await loginApi();
  const token = session.access_token;
  const uid = session.user?.id_usuario ?? 1;
  await abrirCaja(token);

  const browser = await chromium.launch();
  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
    await installLocalApiRoute(ctx, API);
    const page = await ctx.newPage();
    await runFlujosViewport(page, session, token, uid, vp.tag);
    await ctx.close();
  }
  await browser.close();
  console.log(`Capturas en ${OUT_DIR}`);
}

main().catch((e) => {
  console.error(e.stack || e.message);
  process.exit(1);
});
