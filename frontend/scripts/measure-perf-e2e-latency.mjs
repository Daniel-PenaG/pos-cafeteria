/**
 * Latencia E2E navegador (ms). Diálogos nativos auto-aceptados (no miden cierre manual).
 */
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  appendInventarioAMensajeCobro,
  buildResumenInventarioCobro,
} from "../src/utils/cobroAdvertencias.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../../docs/e2e_latencia_navegador.json");
const RUNS = Math.max(5, parseInt(process.env.E2E_LATENCY_RUNS || "5", 10));
const REMOTE_API = "https://pos-cafeteria-api.onrender.com";

function requireEnv(name) {
  const value = (process.env[name] || "").trim();
  if (!value) throw new Error(`Falta ${name}`);
  return value;
}

function pct(vals, p) {
  const s = [...vals].sort((a, b) => a - b);
  if (!s.length) return 0;
  const k = (s.length - 1) * (p / 100);
  const f = Math.floor(k);
  const c = Math.min(f + 1, s.length - 1);
  return f === c ? s[f] : s[f] + (s[c] - s[f]) * (k - f);
}

function stats(vals) {
  return {
    samples: vals.length,
    p50_ms: Math.round(pct(vals, 50) * 100) / 100,
    p95_ms: Math.round(pct(vals, 95) * 100) / 100,
    max_ms: Math.round(Math.max(...vals) * 100) / 100,
  };
}

async function api(base, method, pathName, token, body) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${base.replace(/\/$/, "")}${pathName}`, {
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
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 60000 });
}

async function expandirCatalogo(page) {
  await page.getByPlaceholder(/Buscar producto/i).fill("Latte");
  await page.waitForSelector(".ventas-producto-item", { timeout: 60000 });
}

/** Mismo flujo que capture-perf-flujos (flujo 1). */
async function agregarProductoConPromo(page) {
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
  const t0 = Date.now();
  await prodBtn.click();
  await ctxFirst;
  let hasPromo = false;
  try {
    await page.getByRole("heading", { name: /Aplicar promoción/i }).waitFor({ state: "visible", timeout: 20000 });
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
  if (!lineRes.ok()) throw new Error(`POST lineas ${lineRes.status()}`);
  await page.waitForSelector(".cart-item", { timeout: 15000 });
  return Date.now() - t0;
}

async function main() {
  const BASE = requireEnv("PREVIEW_URL");
  const API = requireEnv("API_URL");
  const user = requireEnv("CAPTURE_LOGIN");
  const pass = requireEnv("CAPTURE_PASSWORD");

  const session = await api(API, "POST", "/auth/login", null, {
    usuario_login: user,
    password: pass,
  });
  if (session.status !== 200 || !session.body.access_token) throw new Error("Login API falló");
  const token = session.body.access_token;
  const uid = session.body.user?.id_usuario ?? 1;

  const ses = await api(API, "GET", "/caja/sesion-actual", token);
  if (!(ses.status === 200 && ses.body?.abierta)) {
    await api(API, "POST", "/caja/apertura", token, {
      efectivo_inicial: 500,
      operation_id: crypto.randomUUID(),
    });
  }

  const producto = [];
  const confirmar = [];
  const listo = [];
  const cobrar = [];
  const inventario = [];
  const pendientes = [];

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await installLocalApiRoute(ctx, API);

  for (let i = 0; i < RUNS; i++) {
    const mesa = i + 1;
    const page = await ctx.newPage();
    page.on("dialog", (d) => d.accept().catch(() => {}));
    await loginPage(page, BASE, user, pass);

    const catalogWait = page.waitForResponse(
      (r) => r.url().includes("/catalogo/productos") && r.status() === 200,
      { timeout: 60000 }
    );
    await page.goto(`${BASE}/ventas?mesa=${mesa}`, { waitUntil: "domcontentloaded" });
    await catalogWait;
    await page.waitForSelector(".ventas-mesas-bar__actual", { timeout: 30000 });
    await expandirCatalogo(page);
    producto.push(await agregarProductoConPromo(page));

    await api(API, "POST", `/pedidos/mesa/${mesa}/lineas?id_usuario=${uid}`, token, {
      id_producto: 1,
      cantidad: 1,
      precio_unitario: 48,
      extras: [],
      operation_id: crypto.randomUUID(),
    });
    await page.reload();
    await page.waitForTimeout(400);
    const tConf = Date.now();
    const confResp = page.waitForResponse(
      (r) => r.url().includes("/confirmar-comanda") && r.request().method() === "POST" && r.status() < 300,
      { timeout: 60000 }
    );
    await page.getByRole("button", { name: /Confirmar pedido/i }).click();
    await confResp;
    await page.goto(`${BASE}/comandera`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".comandera-item", { timeout: 30000 });
    confirmar.push(Date.now() - tConf);

    const hits = [];
    const onPend = (req) => {
      if (req.method() === "GET" && req.url().includes("/comandera/pendientes")) hits.push(Date.now());
    };
    page.on("request", onPend);
    const tListo = Date.now();
    const listoResp = page.waitForResponse(
      (r) => r.url().includes("/listo") && r.request().method() === "POST" && r.status() < 300,
      { timeout: 60000 }
    );
    const markTs = Date.now();
    await page.getByRole("button", { name: /1 listo|listo/i }).first().click();
    await listoResp;
    listo.push(Date.now() - tListo);
    pendientes.push(hits.filter((ts) => ts >= markTs && ts - markTs < 800).length);
    page.off("request", onPend);

    await page.goto(`${BASE}/ventas?mesa=${mesa}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(500);
    const tCob = Date.now();
    const cobResp = page.waitForResponse(
      (r) => r.url().includes("/cobrar") && r.request().method() === "POST" && r.status() < 300,
      { timeout: 90000 }
    );
    await page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i }).scrollIntoViewIfNeeded();
    await page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i }).click();
    await page.waitForSelector(".modal-box--cobro", { timeout: 15000 });
    const monto = page.locator("#monto-recibido");
    if (await monto.count()) {
      const totalTxt = await page.locator(".modal-box--cobro .cart-total").first().innerText();
      const num = (totalTxt.match(/[\d.]+/) || ["100"])[0];
      await monto.fill(num);
    }
    await page.getByRole("button", { name: /Cobrar sin cliente/i }).click({ timeout: 60000 });
    await cobResp;
    cobrar.push(Date.now() - tCob);

    const avisos = [{ nombre: "Leche synth", requerido: 100, disponible: 1 }];
    const msg = appendInventarioAMensajeCobro("OK.", avisos);
    const resumen = buildResumenInventarioCobro(avisos);
    const tInv = Date.now();
    await page.evaluate(
      ({ msgText, resumenText, esResumido }) => {
        const box = document.createElement("div");
        box.setAttribute("data-capture-inv", "1");
        box.className = "modal-overlay";
        box.style.cssText =
          "position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;z-index:9999";
        const inner = document.createElement("div");
        inner.className = "modal-box";
        inner.style.maxWidth = "420px";
        inner.textContent = msgText;
        box.appendChild(inner);
        document.body.appendChild(box);
        if (esResumido) {
          const hint = document.createElement("p");
          hint.className = "hint";
          hint.textContent = resumenText;
          inner.prepend(hint);
        }
      },
      { msgText: msg, resumenText: resumen.texto, esResumido: resumen.esResumido }
    );
    await page.waitForSelector("[data-capture-inv]", { timeout: 5000 });
    inventario.push(Date.now() - tInv);
    await page.close();
  }

  await browser.close();

  const doc = {
    methodology: {
      runs: RUNS,
      viewport: "1366x768",
      note: "Tiempos en navegador hasta respuesta HTTP o DOM utilizable; diálogos auto-aceptados.",
    },
    flujos: [
      { flujo: "producto_toque_pedido_actualizado", ...stats(producto) },
      { flujo: "confirmar_to_comandera_visible", ...stats(confirmar) },
      { flujo: "listo_uno_actualizacion_local", ...stats(listo) },
      { flujo: "cobrar_respuesta_venta", ...stats(cobrar) },
      { flujo: "advertencia_inventario_ui_utilizable", ...stats(inventario) },
    ],
    comandera_sin_get_pendientes_inmediato: {
      muestras: pendientes.length,
      max_gets_en_800ms_tras_listo: Math.max(0, ...pendientes),
      cumple: Math.max(0, ...pendientes) === 0,
    },
  };

  await writeFile(OUT, `${JSON.stringify(doc, null, 2)}\n`, "utf8");
  console.log(`E2E latencia → ${OUT}`);
}

main().catch((e) => {
  console.error(e.stack || e.message);
  process.exit(1);
});
