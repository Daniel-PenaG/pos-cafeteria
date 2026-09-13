import { createOperationId, isNetworkRetryError } from "./operationId.js";

function extrasCanon(extras) {
  return (extras || [])
    .map((e) => ({
      id_extra: e.id_extra ?? null,
      precio: Number(e.precio || 0).toFixed(2),
    }))
    .sort((a, b) => String(a.id_extra).localeCompare(String(b.id_extra)));
}

/** Huella estable de un agregado de línea. Producto y combo no pueden coincidir. */
export function fingerprintLinea({
  numeroMesa,
  paraLlevar = false,
  id_producto,
  cantidad = 1,
  precio_unitario,
  id_promocion = null,
  extras = [],
  comentario = null,
  enviar_comanda = false,
}) {
  return JSON.stringify({
    tipo: "linea",
    numero_mesa: Number(numeroMesa),
    para_llevar: Boolean(paraLlevar),
    id_producto,
    cantidad: Number(cantidad),
    precio_unitario: Number(precio_unitario).toFixed(2),
    id_promocion: id_promocion ?? null,
    extras: extrasCanon(extras),
    comentario: (comentario || "").trim() || null,
    enviar_comanda: Boolean(enviar_comanda),
  });
}

export function fingerprintCombo({
  numeroMesa,
  paraLlevar = false,
  id_promocion,
  cantidad = 1,
  enviar_comanda = false,
}) {
  return JSON.stringify({
    tipo: "combo",
    numero_mesa: Number(numeroMesa),
    para_llevar: Boolean(paraLlevar),
    id_promocion,
    cantidad: Number(cantidad),
    enviar_comanda: Boolean(enviar_comanda),
  });
}

/**
 * Una clave pendiente solo se reutiliza para reintentar el mismo payload.
 * Una selección nueva (otro producto, combo o datos) obtiene UUID nuevo.
 */
export function createIntentStore() {
  const pending = new Map();

  function beginIntent(fingerprint) {
    const existing = pending.get(fingerprint);
    if (existing) return existing;
    const operationId = createOperationId();
    pending.set(fingerprint, operationId);
    return operationId;
  }

  function completeIntent(fingerprint) {
    pending.delete(fingerprint);
  }

  function peek(fingerprint) {
    return pending.get(fingerprint) ?? null;
  }

  function size() {
    return pending.size;
  }

  return { beginIntent, completeIntent, peek, size };
}

/** Un reintento automático con la misma clave y los mismos datos tras timeout/red. */
export async function withIntentRetry(run, { isRetryable = isNetworkRetryError } = {}) {
  try {
    return await run();
  } catch (err) {
    if (isRetryable(err)) {
      return await run();
    }
    throw err;
  }
}

export function shouldKeepPendingKey(err) {
  return isNetworkRetryError(err);
}
