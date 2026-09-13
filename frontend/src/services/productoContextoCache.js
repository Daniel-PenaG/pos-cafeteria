/**
 * TTL 30s: una promoción que empieza o termina no queda minutos desactualizada.
 * El backend revalida precios y promociones al agregar.
 */
export const PRODUCTO_CONTEXTO_TTL_MS = 30_000;

export function createContextoCache(ttlMs = PRODUCTO_CONTEXTO_TTL_MS) {
  const map = new Map();
  return {
    clear() {
      map.clear();
    },
    prune(now = Date.now()) {
      for (const [key, entry] of map.entries()) {
        if (!entry || entry.expiresAt <= now) map.delete(key);
      }
    },
    get(idProducto, now = Date.now()) {
      const entry = map.get(idProducto);
      if (!entry || entry.expiresAt <= now) {
        if (entry) map.delete(idProducto);
        return null;
      }
      return entry.data;
    },
    set(idProducto, data, now = Date.now()) {
      map.set(idProducto, { data, expiresAt: now + ttlMs });
    },
  };
}
