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
import {
  E2E_PRODUCT_CON_PROMO,
  E2E_PRODUCT_SIN_PROMO,
  expandirCatalogo,
  esperarAgregarHabilitado,
  esperarFormularioProducto,
  esperarModalPromocion,
  isContextoResponse,
  isPostLineaResponse,
  rechazarPromoYCalcular,
  stats,
} from "./perf-e2e-shared.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../../docs/e2e_latencia_navegador.json");
const WARMUP = Math.max(0, parseInt(process.env.E2E_LATENCY_WARMUP || "2", 10));
const RUNS = Math.max(10, parseInt(process.env.E2E_LATENCY_RUNS || "10", 10));
const REMOTE_API = "https://pos-cafeteria-api.onrender.com";

function requireEnv(name) {
  const value = (process.env[name] || "").trim();
  if (!value) throw new Error(`Falta ${name}`);
  return value;
}

function pushMetric(buckets, key, value) {
  if (!buckets[key]) buckets[key] = [];
  buckets[key].push(value);
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

async function irVentasMesa(page, base, mesa) {
  const catalogWait = page.waitForResponse(
    (r) => r.url().includes("/catalogo/productos") && r.status() === 200,
    { timeout: 60000 }
  );
  await page.goto(`${base}/ventas?mesa=${mesa}`, { waitUntil: "domcontentloaded" });
  await catalogWait;
  await page.waitForSelector(".ventas-mesas-bar__actual", { timeout: 30000 });
}

async function medirAgregarSinPromo(page, buckets) {
  await expandirCatalogo(page, E2E_PRODUCT_SIN_PROMO);
  const prodBtn = page.locator(".ventas-producto-item").first();
  await prodBtn.scrollIntoViewIfNeeded();

  const ctxFirst = page.waitForResponse(isContextoResponse, { timeout: 60000 });

  const t0 = Date.now();
  await prodBtn.click();
  await ctxFirst;
  const tContexto = Date.now();
  pushMetric(buckets, "sin_promo.click_producto_a_contexto", tContexto - t0);

  await esperarFormularioProducto(page);
  const tForm = Date.now();
  pushMetric(buckets, "sin_promo.contexto_a_modal_o_formulario", tForm - tContexto);

  await esperarAgregarHabilitado(page);
  const agregarBtn = page.getByRole("button", { name: /Agregar al pedido/i });
  const postLinea = page.waitForResponse(isPostLineaResponse, { timeout: 90000 });
  const tClickAg = Date.now();
  await agregarBtn.click();
  const lineRes = await postLinea;
  if (!lineRes.ok()) throw new Error(`POST lineas ${lineRes.status()}`);
  const tPost = Date.now();
  pushMetric(buckets, "sin_promo.click_agregar_a_respuesta_post", tPost - tClickAg);

  await page.waitForSelector(".cart-item", { timeout: 15000 });
  const tCart = Date.now();
  pushMetric(buckets, "sin_promo.respuesta_post_a_pedido_actualizado", tCart - tPost);
  pushMetric(buckets, "sin_promo.flujo_total_sin_promo", tCart - t0);
}

async function medirAgregarConPromo(page, buckets) {
  await expandirCatalogo(page, E2E_PRODUCT_CON_PROMO);
  const prodBtn = page.locator(".ventas-producto-item").first();
  await prodBtn.scrollIntoViewIfNeeded();

  const ctxFirst = page.waitForResponse(isContextoResponse, { timeout: 60000 });

  const t0 = Date.now();
  await prodBtn.click();
  await ctxFirst;
  const tContexto = Date.now();
  pushMetric(buckets, "con_promo.click_producto_a_contexto", tContexto - t0);

  await esperarModalPromocion(page);
  const tPromo = Date.now();
  pushMetric(buckets, "con_promo.contexto_a_modal_o_formulario", tPromo - tContexto);

  await rechazarPromoYCalcular(page);
  const tCalc = Date.now();

  const agregarBtn = page.getByRole("button", { name: /Agregar al pedido/i });
  const postLinea = page.waitForResponse(
    (r) => r.url().includes("/lineas") && r.request().method() === "POST",
    { timeout: 90000 }
  );
  await agregarBtn.click();
  const lineRes = await postLinea;
  if (!lineRes.ok()) {
    const body = await lineRes.text().catch(() => "");
    throw new Error(`POST lineas ${lineRes.status()} ${body.slice(0, 200)}`);
  }
  const tPost = Date.now();
  pushMetric(buckets, "con_promo.click_agregar_a_respuesta_post", tPost - tCalc);

  await page.waitForSelector(".cart-item", { timeout: 15000 });
  const tCart = Date.now();
  pushMetric(buckets, "con_promo.respuesta_post_a_pedido_actualizado", tCart - tPost);
  pushMetric(buckets, "con_promo.flujo_total_con_promo", tCart - t0);
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

  const catalog = await api(API, "GET", "/catalogo/productos", token);
  const catList = Array.isArray(catalog.body) ? catalog.body : [];
  const prodSinPromo = catList.find((p) => p.nombre === E2E_PRODUCT_SIN_PROMO);
  if (!prodSinPromo?.id_producto) {
    throw new Error(`Catálogo E2E sin «${E2E_PRODUCT_SIN_PROMO}» (¿seed_e2e_capture?)`);
  }
  const ctxSin = await api(API, "GET", `/ventas/productos/${prodSinPromo.id_producto}/contexto`, token);
  const precioSin =
    ctxSin.body?.calculo_inicial?.precio_unitario ?? prodSinPromo.precio_venta ?? prodSinPromo.precio;

  const ses = await api(API, "GET", "/caja/sesion-actual", token);
  if (!(ses.status === 200 && ses.body?.abierta)) {
    await api(API, "POST", "/caja/apertura", token, {
      efectivo_inicial: 500,
      operation_id: crypto.randomUUID(),
    });
  }

  const buckets = {};
  const pendientes = [];

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await installLocalApiRoute(ctx, API);

  const totalIter = WARMUP + RUNS;
  for (let i = 0; i < totalIter; i++) {
    const record = i >= WARMUP;
    const mesaSin = 1 + i * 4;
    const mesaCon = mesaSin + 1;
    const mesaConf = mesaSin + 2;
    const mesaCob = mesaSin + 3;
    const page = await ctx.newPage();
    page.on("dialog", (d) => d.accept().catch(() => {}));
    await loginPage(page, BASE, user, pass);

    await irVentasMesa(page, BASE, mesaSin);
    if (record) await medirAgregarSinPromo(page, buckets);
    else await medirAgregarSinPromo(page, {});

    await irVentasMesa(page, BASE, mesaCon);
    if (record) await medirAgregarConPromo(page, buckets);
    else await medirAgregarConPromo(page, {});

    await api(API, "POST", `/pedidos/mesa/${mesaConf}/lineas?id_usuario=${uid}`, token, {
      id_producto: prodSinPromo.id_producto,
      cantidad: 1,
      precio_unitario: precioSin,
      extras: [],
      operation_id: crypto.randomUUID(),
    });
    await irVentasMesa(page, BASE, mesaConf);
    await page.waitForSelector(".cart-item", { timeout: 15000 });
    await page.waitForFunction(
      () => {
        const btn = [...document.querySelectorAll("button")].find((b) =>
          (b.textContent || "").includes("Confirmar pedido")
        );
        return btn && !btn.disabled;
      },
      null,
      { timeout: 30000 }
    );
    const tConf = Date.now();
    const confResp = page.waitForResponse(
      (r) =>
        r.url().includes("/confirmar-comanda") &&
        r.request().method() === "POST" &&
        r.status() < 300,
      { timeout: 60000 }
    );
    await page.getByRole("button", { name: /Confirmar pedido/i }).click();
    await confResp;
    const tConfPost = Date.now();
    if (record) {
      pushMetric(buckets, "click_confirmar_a_respuesta_post", tConfPost - tConf);
    }
    await page.goto(`${BASE}/comandera`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".comandera-item", { timeout: 30000 });
    if (record) {
      pushMetric(buckets, "confirmar_to_comandera_visible", Date.now() - tConf);
    }

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
    if (record) {
      pushMetric(buckets, "listo_uno_actualizacion_local", Date.now() - tListo);
      pendientes.push(hits.filter((ts) => ts >= markTs && ts - markTs < 800).length);
    }
    page.off("request", onPend);

    await page.goto(`${BASE}/ventas?mesa=${mesaCob}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".ventas-mesas-bar__actual", { timeout: 30000 });
    await api(API, "POST", `/pedidos/mesa/${mesaCob}/lineas?id_usuario=${uid}`, token, {
      id_producto: prodSinPromo.id_producto,
      cantidad: 1,
      precio_unitario: precioSin,
      extras: [],
      operation_id: crypto.randomUUID(),
    });
    const pedCob = await api(API, "GET", `/pedidos/mesa/${mesaCob}?id_usuario=${uid}`, token);
    await api(API, "POST", `/pedidos/${pedCob.body.id_pedido}/confirmar-comanda`, token);
    await page.reload();
    await page.waitForSelector(".cart-item", { timeout: 15000 });
    await page.waitForFunction(
      () => {
        const btn = [...document.querySelectorAll("button")].find((b) =>
          /Cerrar cuenta|Cobrar/i.test(b.textContent || "")
        );
        return btn && !btn.disabled;
      },
      null,
      { timeout: 30000 }
    );

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
    const tFinalCob = Date.now();
    await page.getByRole("button", { name: /Cobrar sin cliente/i }).click({ timeout: 60000 });
    await cobResp;
    const tCobPost = Date.now();
    if (record) {
      pushMetric(buckets, "cobrar_modal_y_campos_a_respuesta", tCobPost - tCob);
      pushMetric(buckets, "click_final_cobrar_a_respuesta_post", tCobPost - tFinalCob);
    }

    if (record) {
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
      pushMetric(buckets, "advertencia_inventario_render_sintetico", Date.now() - tInv);
    }

    await page.close();
  }

  await browser.close();

  const sinPromoKeys = [
    "click_producto_a_contexto",
    "contexto_a_modal_o_formulario",
    "click_agregar_a_respuesta_post",
    "respuesta_post_a_pedido_actualizado",
    "flujo_total_sin_promo",
  ];
  const conPromoKeys = [
    "click_producto_a_contexto",
    "contexto_a_modal_o_formulario",
    "click_agregar_a_respuesta_post",
    "respuesta_post_a_pedido_actualizado",
    "flujo_total_con_promo",
  ];
  const otrosKeys = [
    "click_confirmar_a_respuesta_post",
    "confirmar_to_comandera_visible",
    "listo_uno_actualizacion_local",
    "click_final_cobrar_a_respuesta_post",
    "cobrar_modal_y_campos_a_respuesta",
    "advertencia_inventario_render_sintetico",
  ];

  const mapGroup = (prefix, keys) =>
    Object.fromEntries(keys.map((k) => [k, { ...stats(buckets[`${prefix}.${k}`] || []) }]));

  const doc = {
    methodology: {
      warmup: WARMUP,
      runs: RUNS,
      viewport: "1366x768",
      productos_seed: { sin_promo: E2E_PRODUCT_SIN_PROMO, con_promo: E2E_PRODUCT_CON_PROMO },
      note: "Segmentos medidos sin esperas negativas largas; rama UI con Promise.race ≤800 ms fuera del cronómetro de segmentos compuestos.",
    },
    mediciones_invalidadas: [
      {
        flujo: "producto_toque_pedido_actualizado",
        commit: "f6b1d8f7789c0cee17ddee9acf7160f80dd44cfa",
        p50_ms: 20303,
        p95_ms: 20346.4,
        max_ms: 20352,
        motivo:
          "La medición incluía un timeout negativo fijo de 20 segundos esperando un modal de promoción que no aparecía.",
      },
    ],
    metricas: {
      sin_promocion: mapGroup("sin_promo", sinPromoKeys),
      con_promocion: mapGroup("con_promo", conPromoKeys),
      otros: Object.fromEntries(otrosKeys.map((k) => [k, { ...stats(buckets[k] || []) }])),
    },
    metricas_compuestas: {
      confirmar_to_comandera_visible: {
        descripcion: "Clic Confirmar → POST confirmar → navegación y lista Comandera visible",
        ...stats(buckets.confirmar_to_comandera_visible || []),
      },
      cobrar_modal_y_campos_a_respuesta: {
        descripcion: "Abrir modal de cobro, rellenar monto y POST /cobrar",
        ...stats(buckets.cobrar_modal_y_campos_a_respuesta || []),
      },
    },
    prueba_renderizado: {
      advertencia_inventario_ui: {
        descripcion: "DOM sintético (no flujo real post-cobro)",
        ...stats(buckets.advertencia_inventario_render_sintetico || []),
      },
    },
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
