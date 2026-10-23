import { getCachedProductoContexto, getProductoContexto } from "./productoContextoService";

const inflight = new Set();
let scheduled = null;

function prefetchOne(idProducto) {
  if (getCachedProductoContexto(idProducto) || inflight.has(idProducto)) {
    return Promise.resolve();
  }
  inflight.add(idProducto);
  return getProductoContexto(idProducto)
    .catch(() => {})
    .finally(() => {
      inflight.delete(idProducto);
    });
}

async function drain(ids, concurrency) {
  let i = 0;
  const workers = Array.from({ length: Math.min(concurrency, ids.length) }, async () => {
    while (i < ids.length) {
      const id = ids[i++];
      await prefetchOne(id);
    }
  });
  await Promise.all(workers);
}

/**
 * Precalienta contexto de productos en idle (agregado rápido sin GET al tocar).
 * @returns {() => void} cancelar schedule pendiente
 */
export function schedulePrefetchProductoContextos(ids, { concurrency = 4 } = {}) {
  const unique = [...new Set(ids)].filter(
    (id) => id != null && !getCachedProductoContexto(id) && !inflight.has(id)
  );
  if (!unique.length) return () => {};

  const run = () => {
    scheduled = null;
    void drain(unique, concurrency);
  };

  if (typeof requestIdleCallback === "function") {
    const handle = requestIdleCallback(run, { timeout: 4000 });
    scheduled = handle;
    return () => {
      if (scheduled === handle) cancelIdleCallback(handle);
    };
  }
  const t = setTimeout(run, 300);
  scheduled = t;
  return () => clearTimeout(t);
}

export function resetPrefetchProductoContextoForTests() {
  inflight.clear();
  scheduled = null;
}
