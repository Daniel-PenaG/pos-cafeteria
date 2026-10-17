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

/** Plan de actualización optimista al marcar listo (sin await). */
export function buildOptimisticListoPlan(linea, cantidadMarcar) {
  const id = linea.id_detalle_pedido;
  const pend = Number(linea.cantidad_pendiente ?? 0);
  const qty = Math.min(Math.max(1, cantidadMarcar), pend);
  const newPend = pend - qty;
  const newLista = Number(linea.cantidad_lista ?? 0) + qty;
  const rollback = { ...linea };
  if (newPend <= 0) {
    return { kind: "remove", id, rollback };
  }
  return {
    kind: "patch",
    id,
    patch: { ...linea, cantidad_pendiente: newPend, cantidad_lista: newLista },
    rollback,
  };
}

export function applyOptimisticListoPlan(lineas, plan) {
  if (plan.kind === "remove") {
    return lineas.filter((l) => l.id_detalle_pedido !== plan.id);
  }
  return lineas.map((l) =>
    l.id_detalle_pedido === plan.id ? { ...l, ...plan.patch } : l
  );
}

/** Restaura una línea tras error de red; no reinserta si el servidor ya la retiró por cancelación. */
export function rollbackOptimisticLinea(lineas, rollback, { allowReinsert = true } = {}) {
  if (!rollback?.id_detalle_pedido) return lineas;
  const id = rollback.id_detalle_pedido;
  const idx = lineas.findIndex((l) => l.id_detalle_pedido === id);
  if (idx >= 0) {
    const next = [...lineas];
    next[idx] = rollback;
    return next;
  }
  if (!allowReinsert) return lineas;
  return [...lineas, rollback];
}

export function isStaleListoOp(opId, currentOpId) {
  return opId !== currentOpId;
}

/** Reconcilia respuesta HTTP; ignora si llegó tarde respecto a otra operación en la misma línea. */
export function reconcileListoServerLine(lineas, serverDetalle, { stale = false } = {}) {
  if (stale || !serverDetalle?.id_detalle_pedido) return lineas;
  return aplicarLineaListo(lineas, serverDetalle);
}
