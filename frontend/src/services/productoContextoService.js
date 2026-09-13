import api from "../api/axios";
import { useAuthStore } from "../store/authStore";
import { createContextoCache, PRODUCTO_CONTEXTO_TTL_MS } from "./productoContextoCache";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export { PRODUCTO_CONTEXTO_TTL_MS };

const contextoCache = createContextoCache();

export function invalidateProductoContextoCache() {
  contextoCache.clear();
}

export function pruneProductoContextoCache(now = Date.now()) {
  contextoCache.prune(now);
}

export function getCachedProductoContexto(idProducto, now = Date.now()) {
  return contextoCache.get(idProducto, now);
}

export function setCachedProductoContexto(idProducto, data, now = Date.now()) {
  contextoCache.set(idProducto, data, now);
}

export async function getProductoContexto(idProducto, { signal } = {}) {
  const cached = contextoCache.get(idProducto);
  if (cached) {
    return cached;
  }
  const res = await api.get(`/ventas/productos/${idProducto}/contexto`, {
    headers: getAuthHeader(),
    signal,
  });
  contextoCache.set(idProducto, res.data);
  return res.data;
}
