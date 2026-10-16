/** Resumen inventario post-cobro: evita alert() con listas enormes. */

const MAX_LINEAS_RESUMEN = 3;
const MAX_CHARS_ALERT_INVENTARIO = 1200;

export function formatLineaAdvertenciaInventario(a) {
  if (typeof a === "string") return a;
  const falta = Number(a.requerido) - Number(a.disponible);
  return `${a.nombre}: falta ${falta.toFixed(2)}`;
}

export function buildResumenInventarioCobro(avisosInv, { maxLineas = MAX_LINEAS_RESUMEN } = {}) {
  if (!avisosInv?.length) {
    return { lineas: [], total: 0, texto: "", esResumido: false };
  }
  const n = avisosInv.length;
  const lineas = avisosInv.slice(0, maxLineas).map(formatLineaAdvertenciaInventario);
  let texto = lineas.join("\n");
  if (n > maxLineas) {
    texto += `\n… y ${n - maxLineas} más (revisa reportes de consumo).`;
  }
  const esResumido = n > maxLineas;
  return { lineas, total: n, texto, esResumido };
}

/** true si el mensaje completo de cobro respeta límite razonable (no lista gigante). */
export function mensajeCobroInventarioAcotado(msg) {
  if (!msg || msg.length <= MAX_CHARS_ALERT_INVENTARIO) return true;
  const repeticiones = (msg.match(/Stock insuficiente/g) || []).length;
  return repeticiones <= MAX_LINEAS_RESUMEN + 1;
}

export function appendInventarioAMensajeCobro(msgBase, avisosInv) {
  const { total, texto } = buildResumenInventarioCobro(avisosInv);
  if (!total) return msgBase;
  return `${msgBase}\n\n⚠ Inventario (${total} insumo${total === 1 ? "" : "s"}): la venta se completó.\n${texto}`;
}
