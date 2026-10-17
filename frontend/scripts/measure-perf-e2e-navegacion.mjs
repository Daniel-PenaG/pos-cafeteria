/**
 * Latencia de navegación operativa (autocontenido vía run-perf-e2e.ps1).
 */
import { execSync } from "node:child_process";
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  E2E_PRODUCT_SIN_PROMO,
  clickSidebarNav,
  expandirCatalogo,
  esperarAgregarHabilitado,
  esperarFormularioProducto,
  isContextoResponse,
  isPostLineaResponse,
  stats,
} from "./perf-e2e-shared.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../../docs/e2e_latencia_navegacion.json");
const NAV_WARMUP = Math.max(0, parseInt(process.env.E2E_NAV_WARMUP || "2", 10));
const NAV_RUNS = Math.max(10, parseInt(process.env.E2E_NAV_RUNS || "10", 10));
const LISTO_WARMUP = Math.max(0, parseInt(process.env.E2E_LISTO_WARMUP || "3", 10));
const LISTO_RUNS = Math.max(30, parseInt(process.env.E2E_LISTO_RUNS || "30", 10));
const REMOTE_API = "https://pos-cafeteria-api.onrender.com";
const BASE_COMMIT = "a44cadb98c87e1d5be666a4c1e79269d4143685e";

function requireEnv(name) {
  const value = (process.env[name] || "").trim();
  if (!value) throw new Error(`Falta ${name} (use run-perf-e2e.ps1)`);
  return value;
}

function gitMeta() {
  let branch = "unknown";
  let head = "";
  let dirty = true;
  try {
    branch = execSync("git rev-parse --abbrev-ref HEAD", { encoding: "utf8" }).trim();
    head = execSync("git rev-parse HEAD", { encoding: "utf8" }).trim();
    const st = execSync("git status --porcelain", { encoding: "utf8" }).trim();
    dirty = st.length > 0;
  } catch {
    /* ignore */
  }
  return { branch, head, dirty };
}

function push(buckets, key, v) {
  if (typeof v !== "number" || !Number.isFinite(v) || v < 0) return;
  if (!buckets[key]) buckets[key] = [];
  buckets[key].push(v);
}

function attachDuplicateTracker(page, duplicates) {
  const inflight = new Map();
  const onReq = (req) => {
    try {
      const u = new URL(req.url());
      if (u.pathname.includes("/assets/") || u.pathname.endsWith(".js") || u.pathname.endsWith(".css")) return;
      if (!u.pathname.match(/^\/(catalogo|pedidos|comandera|ventas|auth|caja|clientes)/)) return;
      const key = `${req.method()} ${u.pathname.split("?")[0]}`;
      const n = (inflight.get(key) || 0) + 1;
      inflight.set(key, n);
      if (n > 1) duplicates.push({ key, at: Date.now() });
      req.response().finally(() => {
        const c = (inflight.get(key) || 1) - 1;
        if (c <= 0) inflight.delete(key);
        else inflight.set(key, c);
      }).catch(() => {});
    } catch {
      /* ignore */
    }
  };
  page.on("request", onReq);
  return () => page.off("request", onReq);
}

async function apiJson(apiBase, method, pathName, token, body) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${apiBase.replace(/\/$/, "")}${pathName}`, {
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

async function loginApi(apiBase, user, pass) {
  const { status, body } = await apiJson(apiBase, "POST", "/auth/login", null, {
    usuario_login: user,
    password: pass,
  });
  if (status !== 200 || !body.access_token) throw new Error(`Login API falló (${status})`);
  return body;
}

async function abrirCajaSiFalta(apiBase, token) {
  const ses = await apiJson(apiBase, "GET", "/caja/sesion-actual", token);
  if (ses.status === 200 && ses.body?.abierta) return;
  await apiJson(apiBase, "POST", "/caja/apertura", token, {
    efectivo_inicial: 500,
    operation_id: crypto.randomUUID(),
  });
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
  const loginResp = page.waitForResponse(
    (r) => r.url().includes("/auth/login") && r.request().method() === "POST",
    { timeout: 60000 }
  );
  await page.getByRole("button", { name: /Entrar al sistema/i }).click();
  const resp = await loginResp;
  if (resp.status() >= 400) {
    const body = await resp.text().catch(() => "");
    throw new Error(`Login UI falló HTTP ${resp.status()}: ${body.slice(0, 200)}`);
  }
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 60000 });
}

async function clearOperationalCaches(page) {
  await page.evaluate(async () => {
    await window.__posE2e?.clearOperationalSession?.();
  });
}

async function agregarLineaUi(page) {
  await expandirCatalogo(page, E2E_PRODUCT_SIN_PROMO);
  const prodBtn = page.locator(".ventas-producto-item").first();
  const postLinea = page.waitForResponse(isPostLineaResponse, { timeout: 90000 });
  await prodBtn.click();
  await page.waitForResponse(isContextoResponse, { timeout: 60000 });
  await esperarFormularioProducto(page);
  await esperarAgregarHabilitado(page);
  await page.getByRole("button", { name: /Agregar al pedido/i }).click();
  await postLinea;
  await page.waitForSelector('[data-nav-pedido="ready"]', { timeout: 30000 });
}

function isConfirmarPost(r) {
  return r.url().includes("/confirmar-comanda") && r.request().method() === "POST" && r.status() < 300;
}

function isCobroPost(r) {
  return r.url().includes("/cobrar") && r.request().method() === "POST" && r.status() < 300;
}

function isListoPost(r) {
  return r.url().includes("/listo") && r.request().method() === "POST" && r.status() < 300;
}

async function medirVentasCold(page, base, mesa, record, buckets) {
  await clearOperationalCaches(page);
  const t0 = Date.now();
  await page.goto(`${base}/ventas?mesa=${mesa}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-nav-shell="ventas"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_fria_shell_visible", Date.now() - t0);
  const tCat = Date.now();
  await page.waitForSelector('[data-nav-catalog="ready"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_fria_catalogo_visible", Date.now() - tCat);
  const tMesas = Date.now();
  await page.waitForSelector('[data-nav-mesas="ready"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_fria_mesas_visibles", Date.now() - tMesas);
  await agregarLineaUi(page);
  const tPed = Date.now();
  await page.waitForSelector('[data-nav-pedido="ready"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_fria_pedido_visible", Date.now() - tPed);
}

async function medirComanderaAVentas(page, base, mesa, record, buckets) {
  await page.goto(`${base}/ventas?mesa=${mesa}`, { waitUntil: "domcontentloaded" });
  await agregarLineaUi(page);
  await clickSidebarNav(page, /Comandera/i);
  await page.waitForSelector('[data-nav-shell="comandera"]', { timeout: 60000 });

  const tBack = Date.now();
  await clickSidebarNav(page, /Ventas/i);
  const tShell = Date.now();
  await page.waitForSelector('[data-nav-shell="ventas"]', { timeout: 60000 });
  if (record) push(buckets, "comandera_click_ventas_a_shell_visible", Date.now() - tShell);
  const tCat = Date.now();
  await page.waitForSelector('[data-nav-catalog="ready"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_shell_a_catalogo_visible", Date.now() - tCat);
  const tMesas = Date.now();
  await page.waitForSelector('[data-nav-mesas="ready"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_shell_a_mesas_visibles", Date.now() - tMesas);
  const tMesaSel = Date.now();
  await page.waitForSelector(`[data-nav-mesa-seleccionada="${mesa}"]`, { timeout: 60000 });
  if (record) push(buckets, "ventas_mesa_seleccionada_restaurada", Date.now() - tMesaSel);
  const tPed = Date.now();
  await page.waitForSelector('[data-nav-pedido="ready"]', { timeout: 60000 });
  await page.waitForSelector('[data-nav-total-ready="ready"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_shell_a_pedido_activo_visible", Date.now() - tPed);
  if (record) push(buckets, "comandera_a_ventas_total_utilizable", Date.now() - tBack);

  const staleVisible = Date.now();
  const hasCatalog = await page.locator('[data-nav-catalog="ready"]').count();
  if (record && hasCatalog) {
    push(buckets, "ventas_caliente_stale_visible_inmediato", Date.now() - staleVisible);
  }

  await page.evaluate(async () => {
    window.__posE2e?.invalidateCatalogCache?.();
  });
  const tRevStart = Date.now();
  const revBanner = page.locator('[data-nav-revalidating="1"]');
  if (await revBanner.count()) {
    if (record) push(buckets, "ventas_swr_actualizando_visible", Date.now() - tRevStart);
    await revBanner.waitFor({ state: "detached", timeout: 60000 }).catch(() => {});
    if (record) push(buckets, "ventas_swr_revalidacion_fin", Date.now() - tRevStart);
  }
}

async function medirVentasAComandera(page, record, buckets) {
  const t0 = Date.now();
  await clickSidebarNav(page, /Comandera/i);
  const tShell = Date.now();
  await page.waitForSelector('[data-nav-shell="comandera"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_click_comandera_a_shell_visible", Date.now() - tShell);
  const tPed = Date.now();
  await page.waitForSelector('[data-nav-pedidos-ready="ready"]', { timeout: 60000 });
  if (record) push(buckets, "ventas_a_comandera_pedidos_utilizables", Date.now() - tPed);
  if (record) push(buckets, "ventas_a_comandera_total_utilizable", Date.now() - t0);
}

const LISTO_INTERNO_KEYS = [
  "pointerdown_a_handler",
  "click_a_handler",
  "handler_a_dom_optimista",
  "pointerdown_a_dom_optimista",
  "click_a_dom_optimista",
  "dom_optimista_a_inicio_post",
  "request_a_respuesta_http",
  "respuesta_a_reconciliacion",
  "total",
];

function pushFases(buckets, deltas) {
  for (const k of LISTO_INTERNO_KEYS) {
    const v = deltas[k];
    if (v != null) push(buckets, k, v);
  }
}

async function prepararLineaEnComandera(apiBase, page, base, mesa, apiToken, uid, idProducto, precioUnit) {
  const postLine = await apiJson(apiBase, "POST", `/pedidos/mesa/${mesa}/lineas?id_usuario=${uid}`, apiToken, {
    id_producto: idProducto,
    cantidad: 1,
    precio_unitario: precioUnit,
    extras: [],
    operation_id: crypto.randomUUID(),
  });
  if (postLine.status >= 300) {
    throw new Error(`POST línea mesa ${mesa} falló (${postLine.status})`);
  }
  const ped = await apiJson(apiBase, "GET", `/pedidos/mesa/${mesa}?id_usuario=${uid}`, apiToken);
  await apiJson(apiBase, "POST", `/pedidos/${ped.body.id_pedido}/confirmar-comanda`, apiToken);
  await page.goto(`${base}/comandera`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-nav-pedidos-ready="ready"]', { timeout: 60000 });
}

async function medirMarcarListoFases(
  page,
  record,
  faseBuckets,
  pendientes800,
  listoPosts,
  listoPostCounts,
  { recordFases = true, recordPendientes800 = true, listoLongTasksPerSample = null } = {}
) {
  const listoBtn = page.getByRole("button", { name: /^1 listo$/i }).first();
  await listoBtn.waitFor({ state: "visible", timeout: 30000 });
  const hits = [];
  const onPend = (req) => {
    if (req.method() === "GET" && req.url().includes("/comandera/pendientes")) hits.push(Date.now());
  };
  let postsThisSample = 0;
  const onPost = (req) => {
    if (req.method() === "POST" && req.url().includes("/listo")) {
      postsThisSample += 1;
      listoPosts.push(req.url());
    }
  };
  page.on("request", onPend);
  page.on("request", onPost);
  await page.evaluate(() => window.__posE2e?.armListoSample?.());
  const markTs = Date.now();
  const tPlaywrightBeforeClick = Date.now();
  const listoWait = page.waitForResponse(isListoPost, { timeout: 60000 });
  await listoBtn.click();
  const tPlaywrightAfterDispatch = Date.now();
  const domWait = page
    .waitForFunction(
      () =>
        [...document.querySelectorAll(".comandera-listo-btn")].some((b) =>
          (b.textContent || "").includes("Sincronizando")
        ),
      null,
      { timeout: 10000 }
    )
    .then(() => Date.now())
    .catch(() => null);
  await listoWait;
  const tPlaywrightDomWall = await domWait;
  const sample = await page.evaluate(() => ({
    deltas: window.__posE2e?.readListoPhaseDeltasMs?.() || {},
    longtasks: window.__posE2e?.takeListoLongTasks?.() || [],
  }));
  if (record && recordFases && faseBuckets) {
    pushFases(faseBuckets, sample.deltas);
    push(faseBuckets, "playwright_dispatch_wall_clock", tPlaywrightAfterDispatch - tPlaywrightBeforeClick);
    if (tPlaywrightDomWall != null) {
      push(
        faseBuckets,
        "playwright_click_to_dom_syncing_wall",
        tPlaywrightDomWall - tPlaywrightBeforeClick
      );
    }
  }
  if (record && recordFases && faseBuckets && sample.longtasks?.length) {
    const sumLt = sample.longtasks.reduce((acc, e) => acc + (e.duration || 0), 0);
    push(faseBuckets, "longtask_duracion_muestra_ms", sumLt);
  }
  if (record && listoLongTasksPerSample) {
    listoLongTasksPerSample.push(sample.longtasks || []);
  }
  if (record && recordPendientes800 && pendientes800) {
    pendientes800.push(hits.filter((ts) => ts >= markTs && ts - markTs < 800).length);
  }
  page.off("request", onPend);
  page.off("request", onPost);
  if (record && listoPostCounts) listoPostCounts.push(postsThisSample);
}

async function medirConfirmarListoCobro(
  page,
  base,
  mesa,
  record,
  buckets,
  faseBuckets,
  pendientes800,
  listoPosts,
  listoPostCounts,
  apiToken,
  uid,
  idProducto,
  precioUnit
) {
  const apiBase = process.env.API_URL || "http://127.0.0.1:8000";
  const postLine = await apiJson(apiBase, "POST", `/pedidos/mesa/${mesa}/lineas?id_usuario=${uid}`, apiToken, {
    id_producto: idProducto,
    cantidad: 1,
    precio_unitario: precioUnit,
    extras: [],
    operation_id: crypto.randomUUID(),
  });
  if (postLine.status >= 300) {
    throw new Error(`POST línea mesa ${mesa} falló (${postLine.status}): ${JSON.stringify(postLine.body).slice(0, 200)}`);
  }
  await page.goto(`${base}/ventas?mesa=${mesa}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".cart-item", { timeout: 30000 });
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
  const confWait = page.waitForResponse(isConfirmarPost, { timeout: 60000 });
  await page.getByRole("button", { name: /Confirmar pedido/i }).click();
  await confWait;
  if (record) push(buckets, "confirmar_click_a_respuesta_http", Date.now() - tConf);
  const tUi = Date.now();
  await page.waitForSelector(".toast--success", { timeout: 15000 });
  if (record) push(buckets, "confirmar_respuesta_a_ui_confirmada", Date.now() - tUi);

  await clickSidebarNav(page, /Comandera/i);
  await page.waitForSelector('[data-nav-pedidos-ready="ready"]', { timeout: 60000 });
  await medirMarcarListoFases(page, record, null, null, listoPosts, listoPostCounts, {
    recordFases: false,
    recordPendientes800: false,
  });
  if (record) {
    const deltas = await page.evaluate(() => window.__posE2e?.readListoPhaseDeltasMs?.() || {});
    if (deltas.handler_a_visual_local != null) {
      push(buckets, "marcar_listo_click_a_actualizacion_local", deltas.handler_a_visual_local);
    }
  }

  await page.getByRole("link", { name: /Ventas/i }).click();
  await page.waitForSelector('[data-nav-shell="ventas"]', { timeout: 60000 });
  const cobrarBtn = page.getByRole("button", { name: /Cerrar cuenta|Cobrar/i });
  await cobrarBtn.scrollIntoViewIfNeeded();
  let cobroPosts = 0;
  const onCobro = (req) => {
    if (req.method() === "POST" && req.url().includes("/cobrar")) cobroPosts += 1;
  };
  page.on("request", onCobro);
  const tCobro = Date.now();
  const cobWait = page.waitForResponse(isCobroPost, { timeout: 90000 });
  await cobrarBtn.click();
  const modal = page.locator(".modal-box--cobro");
  if (await modal.count()) {
    const monto = modal.locator("#monto-recibido");
    if (await monto.count()) {
      const totalTxt = await modal.locator(".cart-total").first().innerText().catch(() => "100");
      const num = (totalTxt.match(/[\d.]+/) || ["100"])[0];
      await monto.fill(num);
    }
    await modal.getByRole("button", { name: /Cobrar sin cliente/i }).click({ timeout: 60000 });
  }
  await cobWait;
  if (record) push(buckets, "cobrar_click_final_a_respuesta", Date.now() - tCobro);
  const tRes = Date.now();
  await page.waitForSelector('[data-nav-cobro-resumen="visible"]', { timeout: 30000 });
  if (record) push(buckets, "resumen_cobro_visible", Date.now() - tRes);
  const postsBeforeClose = cobroPosts;
  await page.evaluate(() => window.__posE2e?.clearCobroCloseMarks?.());
  const tClose = Date.now();
  await page.getByRole("button", { name: /^Continuar$/i }).click();
  await page
    .waitForFunction(
      () => {
        const el = document.querySelector('[data-nav-cobro-resumen="visible"]');
        if (!el) return true;
        const overlay = el.closest(".modal-overlay");
        if (!overlay) return true;
        return getComputedStyle(overlay).display === "none";
      },
      null,
      { timeout: 10000 }
    )
    .catch(() => {});
  await page.evaluate(
    () =>
      new Promise((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(resolve));
      })
  );
  const cobroMarks = await page.evaluate(() => window.__posE2e?.takeCobroCloseMarks?.() || []);
  if (record) {
    const clickT = cobroMarks.find((m) => m.phase === "close_click")?.t;
    const hiddenT = cobroMarks.find((m) => m.phase === "modal_hidden")?.t;
    const cleanT = cobroMarks.find((m) => m.phase === "cleanup_done")?.t;
    if (clickT != null && hiddenT != null) {
      push(buckets, "cerrar_resumen_click_a_modal_oculto", hiddenT - clickT);
    } else {
      push(buckets, "cerrar_resumen_click_a_modal_oculto", Date.now() - tClose);
    }
    if (hiddenT != null && cleanT != null) {
      push(buckets, "cerrar_resumen_modal_oculto_a_limpieza_interno", cleanT - hiddenT);
    }
    push(buckets, "cerrar_resumen_cobro_limpieza_wall_clock", Date.now() - tClose);
  }
  if (record && cobroPosts > postsBeforeClose) {
    push(buckets, "cobro_post_duplicado_al_cerrar", cobroPosts - postsBeforeClose);
  }
  page.off("request", onCobro);
}

async function main() {
  const BASE = requireEnv("PREVIEW_URL");
  const API = requireEnv("API_URL");
  const user = requireEnv("CAPTURE_LOGIN");
  const pass = requireEnv("CAPTURE_PASSWORD");

  const loginBody = await loginApi(API, user, pass);
  const apiToken = loginBody.access_token;
  const uid = loginBody.user?.id_usuario ?? 1;
  await abrirCajaSiFalta(API, apiToken);

  const catalog = await apiJson(API, "GET", "/catalogo/productos", apiToken);
  const catList = Array.isArray(catalog.body) ? catalog.body : [];
  const prodSinPromo = catList.find((p) => p.nombre === E2E_PRODUCT_SIN_PROMO);
  if (!prodSinPromo?.id_producto) {
    throw new Error(`Seed E2E: falta producto «${E2E_PRODUCT_SIN_PROMO}»`);
  }
  const ctxSin = await apiJson(API, "GET", `/ventas/productos/${prodSinPromo.id_producto}/contexto`, apiToken);
  const precioSin =
    ctxSin.body?.calculo_inicial?.precio_unitario ??
    prodSinPromo.precio_venta ??
    prodSinPromo.precio ??
    0;

  const buckets = {};
  const listoFaseBuckets = {};
  const discarded = [];
  const duplicates = [];
  const pendientes800 = [];
  const listoPostsAll = [];
  const listoPostCounts = [];
  const listoPostCountsNav = [];
  const listoLongTasksPerSample = [];
  const metaGit = gitMeta();

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await installLocalApiRoute(ctx, API);

  const loginPageOnce = await ctx.newPage();
  await loginPage(loginPageOnce, BASE, user, pass);
  await loginPageOnce.close();

  for (let i = 0; i < LISTO_WARMUP + LISTO_RUNS; i++) {
    const record = i >= LISTO_WARMUP;
    const mesa = 40 + (i % 10);
    const page = await ctx.newPage();
    await loginPage(page, BASE, user, pass);
    await prepararLineaEnComandera(API, page, BASE, mesa, apiToken, uid, prodSinPromo.id_producto, precioSin);
    await medirMarcarListoFases(
      page,
      record,
      listoFaseBuckets,
      pendientes800,
      listoPostsAll,
      listoPostCounts,
      { recordFases: true, recordPendientes800: true, listoLongTasksPerSample }
    );
    if (record && listoPostCounts[listoPostCounts.length - 1] !== 1) {
      discarded.push({
        tipo: "listo_post_duplicado",
        mesa,
        count: listoPostCounts[listoPostCounts.length - 1],
      });
    }
    await page.close();
  }

  for (let i = 0; i < NAV_WARMUP + NAV_RUNS; i++) {
    const record = i >= NAV_WARMUP;
    const mesa = 10 + (i % 15);
    const mesaFria = 25 + (i % 15);
    const mesaOp = 35 + (i % 15);
    const page = await ctx.newPage();
    const offDup = attachDuplicateTracker(page, duplicates);
    await loginPage(page, BASE, user, pass);

    await medirVentasCold(page, BASE, mesaFria, record, buckets);
    await medirComanderaAVentas(page, BASE, mesa, record, buckets);
    await medirVentasAComandera(page, record, buckets);
    await medirConfirmarListoCobro(
      page,
      BASE,
      mesaOp,
      record,
      buckets,
      null,
      null,
      listoPostsAll,
      listoPostCountsNav,
      apiToken,
      uid,
      prodSinPromo.id_producto,
      precioSin
    );

    offDup();
    await page.close();
  }

  await browser.close();

  const metricas = Object.fromEntries(Object.keys(buckets).map((k) => [k, stats(buckets[k])]));
  const marcarListoFases = Object.fromEntries(
    Object.keys(listoFaseBuckets).map((k) => [k, stats(listoFaseBuckets[k])])
  );

  const pdDomP95 = marcarListoFases.pointerdown_a_dom_optimista?.p95_ms ?? 9999;
  const clickDomP95 = marcarListoFases.click_a_dom_optimista?.p95_ms ?? 9999;
  const handlerDomP95 = marcarListoFases.handler_a_dom_optimista?.p95_ms ?? 9999;
  const postP95 = marcarListoFases.request_a_respuesta_http?.p95_ms ?? 9999;
  const totalListoP95 = marcarListoFases.total?.p95_ms ?? 9999;

  const objectives = {
    shell_ventas_caliente_p95_lt_300: (metricas.comandera_click_ventas_a_shell_visible?.p95_ms ?? 9999) < 300,
    ventas_fria_shell_p95_lt_1200: (metricas.ventas_fria_shell_visible?.p95_ms ?? 9999) < 1200,
    ventas_fria_catalogo_p95_lt_500: (metricas.ventas_fria_catalogo_visible?.p95_ms ?? 9999) < 500,
    catalogo_caliente_p95_lt_500: (metricas.ventas_shell_a_catalogo_visible?.p95_ms ?? 9999) < 500,
    pedido_restaurado_p95_lt_1000: (metricas.comandera_a_ventas_total_utilizable?.p95_ms ?? 9999) < 1000,
    comandera_a_ventas_p95_lt_1500: (metricas.comandera_a_ventas_total_utilizable?.p95_ms ?? 9999) < 1500,
    ventas_a_comandera_p95_lt_1500: (metricas.ventas_a_comandera_total_utilizable?.p95_ms ?? 9999) < 1500,
    marcar_listo_pointerdown_dom_visible_p95_lt_150: pdDomP95 < 150,
    marcar_listo_click_dom_visible_p95_lt_150: clickDomP95 < 150,
    marcar_listo_handler_dom_p95_lt_16_7: handlerDomP95 < 16.7,
    marcar_listo_post_http_p95_lt_500: postP95 < 500,
    marcar_listo_total_p95_lt_500: totalListoP95 < 500,
    cobro_p95_lt_1000: (metricas.cobrar_click_final_a_respuesta?.p95_ms ?? 9999) < 1000,
    cerrar_resumen_click_modal_oculto_p95_lt_150:
      (metricas.cerrar_resumen_click_a_modal_oculto?.p95_ms ?? 9999) < 150,
    cero_duplicados_concurrentes: duplicates.length === 0,
    cero_get_pendientes_800ms_post_listo: pendientes800.every((n) => n === 0),
    cero_post_listo_duplicados:
      listoPostCounts.every((n) => n === 1) && listoPostCountsNav.every((n) => n === 1),
  };

  const doc = {
    meta: {
      base_commit: BASE_COMMIT,
      branch: metaGit.branch,
      head: metaGit.head,
      local_changes: metaGit.dirty,
      date: new Date().toISOString(),
      nav_warmup: NAV_WARMUP,
      nav_runs: NAV_RUNS,
      listo_warmup: LISTO_WARMUP,
      listo_runs: LISTO_RUNS,
      environment: "local",
      sql_profiler: false,
    },
    objectives,
    marcar_listo_fases_interno: marcarListoFases,
    marcar_listo_fases: marcarListoFases,
    listo_longtasks_por_muestra: listoLongTasksPerSample,
    metricas,
    mediciones_descartadas: discarded,
    duplicados_concurrentes: duplicates.slice(0, 50),
    listo_post_por_muestra: listoPostCounts,
    listo_post_nav_muestras: listoPostCountsNav,
    comandera_sin_get_pendientes_post_listo: {
      muestras: pendientes800,
      cumple: pendientes800.every((n) => n === 0),
    },
  };

  await writeFile(OUT, `${JSON.stringify(doc, null, 2)}\n`, "utf8");
  console.log(`Navegación E2E → ${OUT}`);
}

main().catch((e) => {
  console.error(e.stack || e.message);
  process.exit(1);
});
