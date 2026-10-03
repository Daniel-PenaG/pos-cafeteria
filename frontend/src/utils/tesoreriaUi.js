export function formatoMxn(valor) {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return "$0.00";
  const cents = Math.round(numero * 100) / 100;
  return cents.toLocaleString("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function saldoVisible(entradas, salidas) {
  const e = Math.round(Number(entradas || 0) * 100);
  const s = Math.round(Number(salidas || 0) * 100);
  return (e - s) / 100;
}

export function validarTraspaso({ origen, destino, importe, disponible }) {
  if (!origen || !destino) return "Elige las dos cuentas";
  if (origen === destino) return "La cuenta origen y la destino no pueden ser la misma";
  const monto = Number(importe);
  if (!Number.isFinite(monto) || monto <= 0) return "El importe debe ser mayor a cero";
  if (Number.isFinite(Number(disponible)) && Math.round(monto * 100) > Math.round(Number(disponible) * 100)) {
    return "El importe supera el disponible";
  }
  return "";
}

export function movimientoMonetario(metodo, importe, total) {
  const metodoN = String(metodo || "").toUpperCase();
  if (metodoN === "PUNTOS") return 0;
  if (metodoN.startsWith("PUNTOS")) {
    const remanente = Number(total) - Number(importe);
    return Math.max(0, Math.round(remanente * 100) / 100);
  }
  return Math.round(Number(importe || 0) * 100) / 100;
}

export function esGastoOperativo(tipo) {
  return ["GASTO_OPERATIVO", "COMPRA", "GASTO_CAJA"].includes(tipo);
}

export function efectoErrorTesoreria(status) {
  if (status === 409) return { duplica: false, cierraSesion: false };
  if (status === 403) return { duplica: false, cierraSesion: false };
  return { duplica: false, cierraSesion: status === 401 };
}

export function diferenciaConciliacion(sistema, fisico) {
  return Math.round((Number(fisico || 0) - Number(sistema || 0)) * 100) / 100;
}

export function botonBloqueado(enviando) {
  return Boolean(enviando);
}

export function columnasTesoreria(ancho) {
  if (ancho <= 767) return 1;
  return 3;
}
