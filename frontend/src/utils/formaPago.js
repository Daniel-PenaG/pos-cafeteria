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
};

export function etiquetaFormaPago(forma) {
  if (!forma) return "—";
  return ETIQUETAS[String(forma).toUpperCase()] || forma;
}

export function esEfectivo(forma) {
  return String(forma || "").toUpperCase() === "EFECTIVO";
}

export const FILTROS_FORMA_PAGO = [
  { value: "TODOS", label: "Todos" },
  ...FORMAS_PAGO,
];

export function coincideFiltroPago(forma, filtro) {
  if (!filtro || filtro === "TODOS") return true;
  return String(forma || "").toUpperCase() === filtro;
}
