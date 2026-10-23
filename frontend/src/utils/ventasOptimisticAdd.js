import { sumaImportes } from "./promoCantidad.js";

function lineaMergeable(item, idProducto) {
  if (!item || item.id_producto !== idProducto) return false;
  if (item.estado_linea === "CANCELADA" || Number(item.cantidad) <= 0) return false;
  if (item.en_comanda) return false;
  if (item.extras?.length) return false;
  if (item.id_promocion) return false;
  if (item.sin_promocion === false) return false;
  return true;
}

function subtotalDesdeCalculo(calculo, cantidad) {
  const unit = Number(calculo?.precio_unitario ?? 0);
  const totalLinea = calculo?.total_linea ?? calculo?.subtotal;
  if (cantidad === 1 && totalLinea != null && Number.isFinite(Number(totalLinea))) {
    return Math.round(Number(totalLinea) * 100) / 100;
  }
  return Math.round(unit * cantidad * 100) / 100;
}

/**
 * Actualiza el pedido local al tocar un producto simple (antes de la respuesta POST).
 * @returns {object|null} pedido actualizado o null si no aplica
 */
function nuevaLineaOptimista(producto, calculo, cantidad, extras, comentario, forzarNormal) {
  const subtotal = subtotalDesdeCalculo(calculo, cantidad);
  return {
    id_detalle_pedido: `opt-${producto.id_producto}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    id_producto: producto.id_producto,
    nombre_producto: producto.nombre,
    cantidad,
    cantidad_lista: 0,
    cantidad_pendiente: cantidad,
    precio_unitario: Number(calculo.precio_unitario),
    precio_original: Number(calculo.precio_original_unitario ?? calculo.precio_unitario),
    id_promocion: forzarNormal ? null : calculo.id_promocion ?? null,
    nombre_promocion: forzarNormal ? null : calculo.nombre_promocion ?? null,
    subtotal,
    extras: (extras ?? []).map((e) => ({
      id_extra: e.id_extra,
      nombre: e.nombre,
      precio: Number(e.precio),
    })),
    comentario: comentario || null,
    en_comanda: false,
    estado_linea: "ACTIVA",
    _optimistic: true,
  };
}

/** Modal personalizar: extras, comentario o cantidad > 1 con promos. */
export function aplicarLineaPersonalizadaOptimista(
  pedido,
  producto,
  calculo,
  { cantidad = 1, extras = [], comentario = null, forzar_normal = false } = {}
) {
  if (!pedido?.id_pedido || !producto?.id_producto || !calculo?.margen_ok) return null;
  const cant = Number(cantidad);
  if (!Number.isFinite(cant) || cant < 1) return null;

  if (!extras.length && !comentario && !forzar_normal && !calculo.id_promocion) {
    return aplicarAgregadoOptimista(pedido, producto, calculo, cant);
  }

  const lineas = [...(pedido.lineas ?? [])];
  lineas.push(nuevaLineaOptimista(producto, calculo, cant, extras, comentario, forzar_normal));
  const activas = lineas.filter((l) => l.estado_linea !== "CANCELADA" && Number(l.cantidad) > 0);
  return {
    ...pedido,
    lineas,
    total: sumaImportes(activas),
  };
}

export function aplicarAgregadoOptimista(pedido, producto, calculo, cantidad = 1) {
  if (!pedido?.id_pedido || !producto?.id_producto || !calculo?.margen_ok) return null;

  const lineas = [...(pedido.lineas ?? [])];
  const idx = lineas.findIndex((l) => lineaMergeable(l, producto.id_producto));

  if (idx >= 0) {
    const prev = lineas[idx];
    const nextCant = Number(prev.cantidad) + cantidad;
    const addSub = subtotalDesdeCalculo(calculo, cantidad);
    const nextSub =
      prev.subtotal != null
        ? Math.round((Number(prev.subtotal) + addSub) * 100) / 100
        : subtotalDesdeCalculo(
            { ...calculo, precio_unitario: prev.precio_unitario },
            nextCant
          );
    lineas[idx] = {
      ...prev,
      cantidad: nextCant,
      cantidad_pendiente: nextCant - Number(prev.cantidad_lista || 0),
      subtotal: nextSub,
      _optimistic: true,
    };
  } else {
    lineas.push(nuevaLineaOptimista(producto, calculo, cantidad, [], null, false));
  }

  const activas = lineas.filter((l) => l.estado_linea !== "CANCELADA" && Number(l.cantidad) > 0);
  return {
    ...pedido,
    lineas,
    total: sumaImportes(activas),
  };
}

export function esLineaOptimista(item) {
  return Boolean(item?._optimistic);
}
