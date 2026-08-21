/** Fecha y hora del negocio: America/Mexico_City */

export const MX_TIMEZONE = "America/Mexico_City";

/** YYYY-MM-DD en horario de México */
export function fechaMexicoISO(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: MX_TIMEZONE }).format(date);
}

export function formatearHoraMexico(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("es-MX", {
    timeZone: MX_TIMEZONE,
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatearFechaHoraMexico(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-MX", {
    timeZone: MX_TIMEZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
