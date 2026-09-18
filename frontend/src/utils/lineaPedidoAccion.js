/** Decisión de UI para quitar o corregir una línea del pedido. */

export function esLineaCancelada(item) {
  return item?.estado_linea === "CANCELADA" || Number(item?.cantidad) <= 0;
}

export function esLineaActiva(item) {
  return !esLineaCancelada(item) && Number(item?.cantidad) > 0;
}

export function requiereCancelacionEnviada(item) {
  return Boolean(item?.en_comanda) && esLineaActiva(item);
}

export function accionQuitarLinea(item) {
  if (!item || esLineaCancelada(item)) return "ninguna";
  if (item.en_comanda) return "cancelar_enviada";
  return "eliminar";
}

export function debeRefrescarPedidoPorConflicto(err) {
  return err?.response?.status === 409;
}

export function lineasActivas(lineas) {
  return (lineas ?? []).filter(esLineaActiva);
}
