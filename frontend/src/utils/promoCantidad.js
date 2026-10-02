export const OPCION_PRECIO_NORMAL = "Precio normal";

export function textoPrecioLinea(calc) {
  const aplicaciones = Number(calc?.aplicaciones || 0);
  const normales = Number(calc?.unidades_normales || 0);
  const total = Number(calc?.total_linea ?? calc?.precio_unitario ?? 0);
  const monto = `$${total.toFixed(2)}`;
  if (aplicaciones > 0 && normales > 0) {
    return `${aplicaciones} promoción + ${normales} a precio normal = ${monto}`;
  }
  if (aplicaciones > 0) {
    const veces = aplicaciones === 1 ? "1 promoción" : `${aplicaciones} promociones`;
    return `${veces} = ${monto}`;
  }
  return `Precio normal ${monto}`;
}

export function importeLinea(item) {
  if (item?.subtotal != null && item.subtotal !== "" && Number.isFinite(Number(item.subtotal))) {
    return Math.round(Number(item.subtotal) * 100) / 100;
  }
  if (item?.total_linea != null && Number.isFinite(Number(item.total_linea))) {
    return Math.round(Number(item.total_linea) * 100) / 100;
  }
  return Math.round(Number(item?.cantidad || 0) * Number(item?.precio_unitario || 0) * 100) / 100;
}

export function sumaImportes(lineas) {
  const cents = (lineas || []).reduce((acc, item) => acc + Math.round(importeLinea(item) * 100), 0);
  return cents / 100;
}

export function promoIncompletaBloqueaCobro() {
  return false;
}
