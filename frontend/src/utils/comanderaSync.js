/** Lógica pura de sincronización Comandera (listo, 409, polling). */

export function aplicarLineaListo(lineas, actualizada) {
  const id = actualizada.id_detalle_pedido;
  const pendiente = Number(actualizada.cantidad_pendiente ?? 0);
  if (pendiente <= 0) {
    return lineas.filter((l) => l.id_detalle_pedido !== id);
  }
  return lineas.map((l) =>
    l.id_detalle_pedido === id ? { ...l, ...actualizada, cantidad_pendiente: pendiente } : l
  );
}

/** Evita GET solapado o con pestaña oculta (salvo forzar manual). */
export function shouldSkipComanderaFetch({ cargando, visibilityState, forzar }) {
  if (forzar) return false;
  if (cargando) return true;
  if (visibilityState === "hidden") return true;
  return false;
}

/**
 * Tras mutación Comandera: éxito → estado local; 409 → refrescar; refrescarEnExito → GET.
 * @returns {{ action: 'local'|'refresh'|'none', lineas?: array }}
 */
export function resolveComanderaMutacionExito(data, { refrescarEnExito = false } = {}) {
  if (refrescarEnExito) {
    return { action: "refresh" };
  }
  if (data?.id_detalle_pedido != null) {
    return { action: "local", detalle: data };
  }
  return { action: "none" };
}

export function resolveComanderaMutacionError(status) {
  if (status === 409) {
    return { action: "refresh", notifyConflict: true };
  }
  return { action: "error" };
}
