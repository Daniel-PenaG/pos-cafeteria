/** Valor para input numérico: vacío en lugar de 0 al mostrar. */
export function displayNumberInput(value) {
  if (value === "" || value == null) return "";
  const n = Number(value);
  if (Number.isNaN(n) || n === 0) return "";
  return String(value);
}

/** Cadena vacía → defaultNum (p. ej. stock 0). */
export function parseNumberField(value, defaultNum = 0) {
  if (value === "" || value == null) return defaultNum;
  const n = Number(value);
  return Number.isNaN(n) ? defaultNum : n;
}

/** Carga desde API: 0 se muestra como campo vacío. */
export function numberInputFromApi(value) {
  if (value == null || value === "" || Number(value) === 0) return "";
  return String(value);
}
