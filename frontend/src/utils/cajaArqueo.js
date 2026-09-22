export const DENOMINACIONES_CAJA = [
  { codigo: "B1000", label: "$1,000", valor: 1000, grupo: "Billetes" },
  { codigo: "B500", label: "$500", valor: 500, grupo: "Billetes" },
  { codigo: "B200", label: "$200", valor: 200, grupo: "Billetes" },
  { codigo: "B100", label: "$100", valor: 100, grupo: "Billetes" },
  { codigo: "B50", label: "$50", valor: 50, grupo: "Billetes" },
  { codigo: "B20", label: "$20", valor: 20, grupo: "Billetes" },
  { codigo: "M20", label: "$20", valor: 20, grupo: "Monedas" },
  { codigo: "M10", label: "$10", valor: 10, grupo: "Monedas" },
  { codigo: "M5", label: "$5", valor: 5, grupo: "Monedas" },
  { codigo: "M2", label: "$2", valor: 2, grupo: "Monedas" },
  { codigo: "M1", label: "$1", valor: 1, grupo: "Monedas" },
  { codigo: "M050", label: "$0.50", valor: 0.5, grupo: "Monedas" },
];

export function cantidadesVacias() {
  return Object.fromEntries(DENOMINACIONES_CAJA.map((d) => [d.codigo, ""]));
}

export function totalDesdeDenominaciones(cantidades) {
  return DENOMINACIONES_CAJA.reduce((acc, d) => {
    const n = Number(cantidades[d.codigo] || 0);
    if (!Number.isFinite(n) || n < 0) return acc;
    return Math.round((acc + n * d.valor) * 100) / 100;
  }, 0);
}

export function payloadDenominaciones(cantidades) {
  return DENOMINACIONES_CAJA.map((d) => ({
    codigo: d.codigo,
    cantidad: Math.max(0, parseInt(cantidades[d.codigo] || "0", 10) || 0),
  }));
}

export function etiquetaEstadoCaja(estado) {
  const map = {
    ABIERTA: "Abierta",
    EN_ARQUEO: "En arqueo",
    CERRADA_CONCILIADA: "Cerrada conciliada",
    CERRADA_CON_DIFERENCIA: "Cerrada con diferencia",
    REVISADA: "Revisada",
    ANULADA: "Anulada",
  };
  return map[estado] || estado || "—";
}

export function fmtCaja(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return "$0.00";
  return `$${v.toFixed(2)}`;
}
