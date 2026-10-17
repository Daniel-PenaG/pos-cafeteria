/** Constantes y helpers compartidos para capturas/medición E2E de rendimiento. */

export const E2E_PRODUCT_SIN_PROMO = "E2E Sin Promo";
export const E2E_PRODUCT_CON_PROMO = "E2E Con Promo";
export const PROMO_HEADING = /¿Aplicar promoción\?|Aplicar promoción/i;
export const BRANCH_PROBE_MS = 800;

export function pct(vals, p) {
  const s = [...vals].sort((a, b) => a - b);
  if (!s.length) return 0;
  const k = (s.length - 1) * (p / 100);
  const f = Math.floor(k);
  const c = Math.min(f + 1, s.length - 1);
  return f === c ? s[f] : s[f] + (s[c] - s[f]) * (k - f);
}

export function stats(vals) {
  if (!vals.length) {
    return { samples: 0, p50_ms: 0, p95_ms: 0, max_ms: 0, valores_ms: [] };
  }
  return {
    samples: vals.length,
    p50_ms: Math.round(pct(vals, 50) * 100) / 100,
    p95_ms: Math.round(pct(vals, 95) * 100) / 100,
    max_ms: Math.round(Math.max(...vals) * 100) / 100,
    valores_ms: vals.map((v) => Math.round(v * 100) / 100),
  };
}

export function isContextoResponse(r) {
  return r.url().includes("/contexto") && r.status() === 200;
}

export function isPostLineaResponse(r) {
  return (
    r.url().includes("/pedidos/mesa/") &&
    r.url().includes("/lineas") &&
    r.request().method() === "POST" &&
    r.status() >= 200 &&
    r.status() < 300
  );
}

export async function expandirCatalogo(page, term) {
  await page.getByPlaceholder(/Buscar producto/i).fill(term);
  await page.waitForSelector(".ventas-producto-item", { timeout: 60000 });
}

export async function esperarAgregarHabilitado(page) {
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
}

/** Tras contexto: modal de producto (sin modal de promoción). */
export async function esperarFormularioProducto(page) {
  const promo = page.getByRole("heading", { name: PROMO_HEADING });
  const agregar = page.getByRole("button", { name: /Agregar al pedido/i });
  const winner = await Promise.race([
    promo.waitFor({ state: "visible", timeout: BRANCH_PROBE_MS }).then(() => "promo"),
    agregar.waitFor({ state: "visible", timeout: BRANCH_PROBE_MS }).then(() => "form"),
  ]).catch(() => "timeout");
  if (winner === "promo") {
    throw new Error("Se esperaba formulario de producto sin promoción");
  }
  if (winner !== "form") {
    throw new Error("Formulario de producto no visible tras contexto");
  }
}

/** Tras contexto: modal «¿Aplicar promoción?» (seed E2E Con Promo). */
export async function esperarModalPromocion(page) {
  await page.getByRole("heading", { name: PROMO_HEADING }).waitFor({
    state: "visible",
    timeout: 15000,
  });
}

export async function rechazarPromoYCalcular(page) {
  await page.getByRole("button", { name: /No, precio normal/i }).click();
  await page.waitForResponse(
    (r) =>
      r.url().includes("/promociones/calcular") &&
      r.request().method() === "POST" &&
      r.status() === 200,
    { timeout: 60000 }
  );
  await esperarAgregarHabilitado(page);
}

/** Sidebar en móvil (<768px) requiere abrir menú antes del enlace. */
export async function clickSidebarNav(page, labelRegex) {
  const w = page.viewportSize()?.width ?? 1366;
  if (w <= 767) {
    await page.getByRole("button", { name: /Abrir menú/i }).click();
    await page.locator("#app-sidebar-nav").waitFor({ state: "visible", timeout: 15000 });
  }
  await page.locator("#app-sidebar-nav").getByRole("link", { name: labelRegex }).click();
}
