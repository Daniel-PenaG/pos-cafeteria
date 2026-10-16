/** Sincronización local ventas sin GET redundantes. */

export function mergeMesaActivaFromPedido(prev, numeroMesa, pedidoActualizado) {
  if (!numeroMesa || !pedidoActualizado) return prev;
  return {
    ...prev,
    [numeroMesa]: {
      ...(prev[numeroMesa] || {}),
      id_pedido: pedidoActualizado.id_pedido,
      numero_mesa: numeroMesa,
      total: pedidoActualizado.total,
      num_lineas: pedidoActualizado.lineas?.length ?? 0,
      lineas: pedidoActualizado.lineas,
    },
  };
}

/**
 * Efecto tras confirmar comanda: solo GET si no hay cuerpo del POST.
 * @returns {{ usedPostBody: boolean, needsFullReload: boolean }}
 */
export function efectoConfirmarComanda(pedidoActualizado) {
  if (pedidoActualizado?.id_pedido) {
    return { usedPostBody: true, needsFullReload: false };
  }
  return { usedPostBody: false, needsFullReload: true };
}

/** Patrón post-POST línea: merge local únicamente (sin GET /pedidos/activos). */
export function sincronizarTrasAgregarLinea(prevMesas, numeroMesa, pedidoActualizado) {
  return {
    mesas: mergeMesaActivaFromPedido(prevMesas, numeroMesa, pedidoActualizado),
    llamoGetPedidosActivos: false,
  };
}
