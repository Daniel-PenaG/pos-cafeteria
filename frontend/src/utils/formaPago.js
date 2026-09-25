/** Formas de pago — valor interno y etiqueta de UI. TARJETA se muestra como Terminal. */
export const FORMAS_PAGO = [
  { value: "EFECTIVO", label: "Efectivo" },
  { value: "TRANSFERENCIA", label: "Transferencia" },
  { value: "TARJETA", label: "Terminal" },
];

const ETIQUETAS = {
  EFECTIVO: "Efectivo",
  TRANSFERENCIA: "Transferencia",
  TARJETA: "Terminal",
  DESCONOCIDO: "Desconocido",
};

export function etiquetaFormaPago(forma) {
  if (!forma) return "—";
  return ETIQUETAS[String(forma).toUpperCase()] || forma;
}

export function esEfectivo(forma) {
  return String(forma || "").toUpperCase() === "EFECTIVO";
}

/** Nulo/vacío → EFECTIVO histórico. Valor explícito desconocido (PUNTOS, etc.) no es efectivo. */
export function bucketFormaPago(forma) {
  if (forma == null || String(forma).trim() === "") return "EFECTIVO";
  const fp = String(forma).trim().toUpperCase();
  if (fp === "EFECTIVO" || fp === "TRANSFERENCIA" || fp === "TARJETA") return fp;
  return "DESCONOCIDO";
}

export const FILTROS_FORMA_PAGO = [
  { value: "TODOS", label: "Todos" },
  ...FORMAS_PAGO,
];

export function coincideFiltroPago(forma, filtro) {
  if (!filtro || filtro === "TODOS") return true;
  return String(forma || "").toUpperCase() === filtro;
}
