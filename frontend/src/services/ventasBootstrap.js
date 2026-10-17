import {
  fetchCatalogBundle,
  fetchMesasActivasCached,
  fetchMesasConfigCached,
} from "../cache/operationalCaches";

/**
 * Carga inicial Ventas: catálogo, mesas config y mesas activas en paralelo.
 */
export async function bootstrapVentasShell({ force = false } = {}) {
  const opts = { force, allowStale: !force };
  const [catalog, mesasLista, mesasActivas] = await Promise.allSettled([
    fetchCatalogBundle(opts),
    fetchMesasConfigCached(opts),
    fetchMesasActivasCached(opts),
  ]);

  const errors = [];
  const partial = {};

  if (catalog.status === "fulfilled") {
    partial.catalog = catalog.value;
  } else {
    errors.push(catalog.reason);
  }
  if (mesasLista.status === "fulfilled") {
    partial.mesasLista = mesasLista.value;
  } else {
    errors.push(mesasLista.reason);
  }
  if (mesasActivas.status === "fulfilled") {
    partial.mesasActivas = mesasActivas.value;
  } else {
    errors.push(mesasActivas.reason);
  }

  partial.revalidating =
    Boolean(partial.catalog?.stale) ||
    Boolean(partial.mesasLista?.stale) ||
    Boolean(partial.mesasActivas?.stale);

  return { partial, errors };
}
