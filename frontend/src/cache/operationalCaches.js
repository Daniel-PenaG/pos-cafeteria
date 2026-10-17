import { getCategorias, getProductos } from "../services/productosService";
import { getExtraTiposPos } from "../services/extrasVentaService";
import { getMesasConfig, getPedidosActivos } from "../services/pedidosService";
import { invalidateProductoContextoCache } from "../services/productoContextoService";
import { createResourceCache } from "./resourceCache";

export const CATALOG_TTL_MS = 45_000;
export const MESAS_CONFIG_TTL_MS = 45_000;
export const MESAS_ACTIVAS_TTL_MS = 3_000;

function sessionKey() {
  const store = typeof window !== "undefined" ? window.authStore : null;
  const u = store?.getState?.()?.user;
  return u?.id_usuario ? `u:${u.id_usuario}` : "anon";
}

export const catalogCache = createResourceCache({ ttlMs: CATALOG_TTL_MS, sessionKey });
export const mesasConfigCache = createResourceCache({ ttlMs: MESAS_CONFIG_TTL_MS, sessionKey });
export const mesasActivasCache = createResourceCache({ ttlMs: MESAS_ACTIVAS_TTL_MS, sessionKey });

export async function fetchCatalogBundle(options) {
  return catalogCache.load(
    async () => {
      const [prods, cats, tipos] = await Promise.all([
        getProductos(),
        getCategorias(),
        getExtraTiposPos(),
      ]);
      return {
        productos: prods.filter((p) => p.activo !== false),
        categorias: [...cats].sort((a, b) => a.nombre.localeCompare(b.nombre, "es")),
        tiposPosLabels: Object.fromEntries(tipos.map((t) => [t.codigo, t.etiqueta])),
      };
    },
    options
  );
}

export async function fetchMesasConfigCached(options) {
  return mesasConfigCache.load(async () => {
    const data = await getMesasConfig();
    return Array.isArray(data.mesas) ? data.mesas : [1, 2, 3, 4, 5, 6, 7, 8, 9];
  }, options);
}

export async function fetchMesasActivasCached(options) {
  return mesasActivasCache.load(async () => {
    const list = await getPedidosActivos();
    const map = {};
    list.forEach((p) => {
      map[p.numero_mesa] = p;
    });
    return map;
  }, options);
}

export function invalidateMesasActivas() {
  mesasActivasCache.invalidate();
}

export function invalidateCatalogCache() {
  catalogCache.invalidate();
  invalidateProductoContextoCache();
}

export function clearAllOperationalCaches() {
  catalogCache.reset();
  mesasConfigCache.reset();
  mesasActivasCache.reset();
  invalidateProductoContextoCache();
}
