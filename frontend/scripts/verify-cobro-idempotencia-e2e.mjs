/**
 * Verifica idempotencia de cobro vía Playwright + API (una venta, un POST).
 */
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { E2E_PRODUCT_SIN_PROMO, expandirCatalogo, isPostLineaResponse, isContextoResponse, esperarFormularioProducto, esperarAgregarHabilitado } from "./perf-e2e-shared.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../../docs/e2e_cobro_idempotencia.json");
const REMOTE_API = "https://pos-cafeteria-api.onrender.com";

function requireEnv(n) {
  const v = (process.env[n] || "").trim();
  if (!v) throw new Error(`Falta ${n}`);
  return v;
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

async function main() {
  const BASE = requireEnv("PREVIEW_URL");
  const API = requireEnv("API_URL");
  const user = requireEnv("CAPTURE_LOGIN");
  const pass = requireEnv("CAPTURE_PASSWORD");
  const mesa = 18;

  const login = await api(API, "POST", "/auth/login", null, { usuario_login: user, password: pass });
  const token = login.body.access_token;
  const uid = login.body.user?.id_usuario ?? 1;

  const ses = await api(API, "GET", "/caja/sesion-actual", token);
  if (!(ses.status === 200 && ses.body?.abierta)) {
    await api(API, "POST", "/caja/apertura", token, { efectivo_inicial: 500, operation_id: crypto.randomUUID() });
  }

  const prods = await api(API, "GET", "/catalogo/productos", token);
  const prod = (Array.isArray(prods.body) ? prods.body : []).find((p) => p.nombre === E2E_PRODUCT_SIN_PROMO);
  if (!prod) throw new Error("Producto E2E Sin Promo no encontrado");
  const ctx = await api(API, "GET", `/ventas/productos/${prod.id_producto}/contexto`, token);
  const precio = ctx.body?.calculo_inicial?.precio_unitario ?? prod.precio_venta ?? 50;

  await api(API, "POST", `/pedidos/mesa/${mesa}/lineas?id_usuario=${uid}`, token, {
    id_producto: prod.id_producto,
    cantidad: 1,
    precio_unitario: precio,
    extras: [],
    operation_id: crypto.randomUUID(),
  });
  const ped = await api(API, "GET", `/pedidos/mesa/${mesa}?id_usuario=${uid}`, token);
  const idPedido = ped.body.id_pedido;
  await api(API, "POST", `/pedidos/${idPedido}/confirmar-comanda`, token);
  const pend = await api(API, "GET", "/comandera/pendientes", token);
  const linea = (Array.isArray(pend.body) ? pend.body : []).find((l) => l.numero_mesa === mesa);
  if (linea?.id_detalle_pedido) {
    await api(API, "POST", `/comandera/lineas/${linea.id_detalle_pedido}/listo?id_usuario=${uid}`, token, {
      cantidad: 1,
      operation_id: crypto.randomUUID(),
    });
  }

  const browser = await chromium.launch();
  const ctxPw = await browser.newContext();
  await ctxPw.route("**/*", (route) => {
    const url = route.request().url();
    if (url.includes("onrender.com") || url.startsWith(REMOTE_API)) {
      return route.continue({ url: url.replace(REMOTE_API, API) });
    }
    return route.continue();
  });
  const page = await ctxPw.newPage();
  const cobroPosts = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/cobrar")) cobroPosts.push(req.url());
  });

  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.fill("#user", user);
  await page.fill("#pass", pass);
  await page.getByRole("button", { name: /Entrar al sistema/i }).click();
  await page.waitForURL((u) => !u.pathname.endsWith("/login"), { timeout: 60000 });

  await page.goto(`${BASE}/ventas?mesa=${mesa}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".cart-item", { timeout: 30000 });
  const cobrarBtn = page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i });
  await cobrarBtn.scrollIntoViewIfNeeded();
  const cobWait = page.waitForResponse((r) => r.url().includes("/cobrar") && r.request().method() === "POST" && r.status() < 300, { timeout: 90000 });
  await cobrarBtn.click();
  const modal = page.locator(".modal-box--cobro");
  if (await modal.count()) {
    const monto = modal.locator("#monto-recibido");
    if (await monto.count()) {
      const t = await modal.locator(".cart-total").first().innerText();
      await monto.fill((t.match(/[\d.]+/) || ["100"])[0]);
    }
    const cobBtn = modal.getByRole("button", { name: /Cobrar sin cliente/i });
    await cobBtn.dblclick();
  }
  const cobRes = await cobWait;
  const ventaBody = await cobRes.json().catch(() => ({}));
  const idVenta = ventaBody.id_venta;

  await page.waitForSelector('[data-nav-cobro-resumen="visible"]', { timeout: 30000 });
  const postsBeforeClose = cobroPosts.length;
  await page.getByRole("button", { name: /^Continuar$/i }).click();
  await page.waitForTimeout(300);
  await page.getByRole("button", { name: /^Continuar$/i }).click().catch(() => {});
  await page.waitForTimeout(300);

  await page.goto(`${BASE}/comandera`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(200);

  const pedPost = await api(API, "GET", `/pedidos/mesa/${mesa}?id_usuario=${uid}`, token);
  const pedidoBody = pedPost.body || {};
  const totalVenta = Number(ventaBody.total ?? ventaBody.total_venta ?? 0);
  const pagosCobro = Array.isArray(ventaBody.pagos) ? ventaBody.pagos : [];
  const sumPagos = pagosCobro.reduce((s, p) => s + Number(p.monto ?? 0), 0);
  const activos = await api(API, "GET", "/pedidos/activos", token);
  const dupMesa = (Array.isArray(activos.body) ? activos.body : []).filter((p) => p.numero_mesa === mesa);

  const doc = {
    post_cobro_count: cobroPosts.length,
    post_cobro_urls: cobroPosts,
    posts_after_close_modal: cobroPosts.length - postsBeforeClose,
    id_venta: idVenta,
    id_pedido: idPedido,
    cobro_http_status: cobRes.status(),
    pedido_mesa_estado: pedidoBody.estado,
    pagos_sum: sumPagos,
    venta_total: totalVenta,
    mesa_sin_pedido_activo: dupMesa.length === 0,
    single_venta: cobroPosts.length === 1,
    close_modal_no_extra_post: cobroPosts.length === postsBeforeClose,
    route_change_no_extra_post: cobroPosts.length === 1,
    venta_exists: Boolean(idVenta) && cobRes.status() >= 200 && cobRes.status() < 300,
    pagos_match_total: pagosCobro.length ? Math.abs(sumPagos - totalVenta) < 0.02 : true,
    double_tap_single_post: cobroPosts.length === 1,
  };

  await browser.close();
  await writeFile(OUT, `${JSON.stringify(doc, null, 2)}\n`, "utf8");
  if (!doc.single_venta || !doc.close_modal_no_extra_post || !doc.venta_exists) {
    throw new Error(`Idempotencia cobro falló: ${JSON.stringify(doc)}`);
  }
  console.log(`Cobro idempotencia OK → ${OUT}`);
}

main().catch((e) => {
  console.error(e.stack || e.message);
  process.exit(1);
});
