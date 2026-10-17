const ROUTE_LOADERS = {
  "/ventas": () => import("../pages/Ventas"),
  "/comandera": () => import("../pages/Comandera"),
  "/mesas-activas": () => import("../pages/MesasActivas"),
  "/ventas-para-llevar": () => import("../pages/VentasParaLlevar"),
};

const prefetched = new Set();

export function prefetchRoute(path) {
  const loader = ROUTE_LOADERS[path];
  if (!loader || prefetched.has(path)) return;
  prefetched.add(path);
  loader().catch(() => {
    prefetched.delete(path);
  });
}

export function prefetchOperationalRoutesIdle() {
  if (typeof requestIdleCallback !== "function") {
    window.setTimeout(() => {
      Object.keys(ROUTE_LOADERS).forEach(prefetchRoute);
    }, 1200);
    return;
  }
  requestIdleCallback(
    () => {
      Object.keys(ROUTE_LOADERS).forEach(prefetchRoute);
    },
    { timeout: 4000 }
  );
}

export function bindPrefetchHandlers(el, path) {
  if (!el || !ROUTE_LOADERS[path]) return;
  const run = () => prefetchRoute(path);
  el.addEventListener("mouseenter", run, { once: true, passive: true });
  el.addEventListener("focus", run, { once: true });
  el.addEventListener("touchstart", run, { once: true, passive: true });
}

export function resetPrefetchStateForTests() {
  prefetched.clear();
}
