import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

/** Caché por sesión: id_producto → contexto */
const contextoCache = new Map();

export function invalidateProductoContextoCache() {
  contextoCache.clear();
}

export async function getProductoContexto(idProducto, { signal } = {}) {
  if (contextoCache.has(idProducto)) {
    return contextoCache.get(idProducto);
  }
  const res = await api.get(`/ventas/productos/${idProducto}/contexto`, {
    headers: getAuthHeader(),
    signal,
  });
  contextoCache.set(idProducto, res.data);
  return res.data;
}
