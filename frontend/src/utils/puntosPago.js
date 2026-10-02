/** Solicitud de canje. El backend vuelve a calcular equivalencia y máximo. */
export const PUNTOS_POR_PESO = 10;
export const MINIMO_PUNTOS_CANJE = 50;

export function aCentavos(valor) {
  return Math.round(Number(valor) * 100);
}

export function desdeCentavos(centavos) {
  return centavos / 100;
}

function redondear(valor) {
  return desdeCentavos(aCentavos(valor));
}

export function cambioEfectivo(recibido, aCubrir) {
  return desdeCentavos(aCentavos(recibido) - aCentavos(aCubrir));
}

/** Puntos solo sobre el remanente monetario. La parte cubierta con puntos suma 0. */
export function puntosGeneradosEstimados(importeMonetario, pesosPorPunto = 10) {
  const base = aCentavos(pesosPorPunto);
  const dinero = aCentavos(importeMonetario);
  if (base <= 0 || dinero <= 0) return 0;
  return Math.floor(dinero / base);
}

export function saldoFinalEstimado(inicial, usados, generados) {
  return Number(inicial || 0) - Number(usados || 0) + Number(generados || 0);
}

export function ocultaMetodoMonetario(canje) {
  return Boolean(canje && !canje.bloquea && canje.puntos > 0 && Number(canje.importe) === 0);
}

export function exigeMetodoMonetario(canje) {
  return !ocultaMetodoMonetario(canje);
}

export function botonCobroBloqueado({ loading, bloquea }) {
  return Boolean(loading || bloquea);
}

/** 409 conserva el pedido y el modal. SALDO_PUNTOS_CAMBIO refresca el saldo y no reintenta. */
export function resolverErrorCobro(status, data) {
  const anidado = data?.detail;
  const cuerpo = data?.codigo ? data : anidado && typeof anidado === "object" ? anidado : null;
  const codigo = cuerpo?.codigo || null;
  const base = {
    conservaPedido: true,
    cierraModal: false,
    refrescaSaldo: false,
    reintentar: false,
    codigo,
    saldoActual: cuerpo?.saldo_actual ?? null,
  };
  if (status === 409 && codigo === "RECALCULO") {
    return { ...base, confirmaRecalculo: true, refrescaSaldo: false };
  }
  if (status === 409 && codigo === "SALDO_PUNTOS_CAMBIO") {
    return { ...base, refrescaSaldo: true };
  }
  if (status === 409) {
    return { ...base, refrescaSaldo: true };
  }
  return base;
}

export function clientePrecargado(pedido) {
  if (!pedido?.id_cliente) return null;
  return {
    id_cliente: pedido.id_cliente,
    nombre: pedido.cliente_nombre || "Cliente",
    telefono: pedido.cliente_telefono || "",
    puntos_saldo: Number(pedido.cliente_puntos_saldo || 0),
    activo: pedido.cliente_activo !== false,
  };
}

export function evaluarCanjeCliente(total, cliente, raw) {
  if (cliente && cliente.activo === false) {
    const vacio = evaluarCanje(total, cliente.puntos_saldo ?? 0, "");
    return {
      ...vacio,
      error: "El cliente está inactivo",
      bloquea: true,
      habilitado: false,
    };
  }
  return evaluarCanje(total, cliente?.puntos_saldo ?? 0, cliente ? raw : "");
}

export function payloadCobro({
  idUsuario,
  formaPago,
  cliente,
  conCliente,
  puntos,
  operationId,
  desasociarCliente = false,
}) {
  return {
    id_usuario: idUsuario,
    forma_pago: formaPago,
    id_cliente: !desasociarCliente && conCliente && cliente ? cliente.id_cliente : null,
    puntos_canje: !desasociarCliente && conCliente && cliente ? Number(puntos || 0) : 0,
    operation_id: operationId,
    desasociar_cliente: Boolean(desasociarCliente),
  };
}

export function maxPuntosCanje(total, saldo) {
  const cents = Math.round(Number(total) * 100);
  const saldoEntero = Math.floor(Number(saldo) || 0);
  if (!Number.isFinite(cents) || cents < MINIMO_PUNTOS_CANJE * 10) return 0;
  const maxTicket = Math.floor(cents / 100) * PUNTOS_POR_PESO;
  const usable = Math.min(Math.floor(saldoEntero / PUNTOS_POR_PESO) * PUNTOS_POR_PESO, maxTicket);
  return usable >= MINIMO_PUNTOS_CANJE ? usable : 0;
}

export function evaluarCanje(total, saldo, raw) {
  const totalNum = redondear(total);
  const max = maxPuntosCanje(totalNum, saldo);
  const texto = String(raw ?? "").trim();
  const base = {
    puntos: 0,
    equivalencia: 0,
    importe: totalNum,
    max,
    error: null,
    habilitado: max >= MINIMO_PUNTOS_CANJE,
    bloquea: false,
  };
  if (texto === "" || texto === "0") return base;
  if (!/^\d+$/.test(texto)) {
    return { ...base, error: "Indica una cantidad entera de puntos", bloquea: true };
  }
  const n = Number(texto);
  if (n === 0) return base;
  let error = null;
  if (totalNum < MINIMO_PUNTOS_CANJE / PUNTOS_POR_PESO) {
    error = "El ticket es menor a $5. No se puede canjear puntos.";
  } else if (n < MINIMO_PUNTOS_CANJE) {
    error = `El canje mínimo es ${MINIMO_PUNTOS_CANJE} puntos`;
  } else if (n % PUNTOS_POR_PESO !== 0) {
    error = "Solo se canjean múltiplos de 10 puntos";
  } else if (n > Math.floor(Number(saldo) || 0)) {
    error = "Los puntos superan el saldo del cliente";
  } else if (n > max) {
    error = "Los puntos no pueden exceder el total del ticket";
  }
  if (error) return { ...base, error, bloquea: true };
  const equivalencia = desdeCentavos(n * 10);
  return {
    ...base,
    puntos: n,
    equivalencia,
    importe: desdeCentavos(aCentavos(totalNum) - aCentavos(equivalencia)),
  };
}
