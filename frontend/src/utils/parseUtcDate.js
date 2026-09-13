/**
 * Interpreta timestamps de la API como UTC.
 * Si no traen zona (`Z` u offset), se asumen UTC para no usar la zona del dispositivo.
 */
export function parseUtcDate(value) {
  if (value == null || value === "") return null;
  if (value instanceof Date) {
    const t = value.getTime();
    return Number.isNaN(t) ? null : value;
  }
  const raw = String(value).trim();
  if (!raw) return null;
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw);
  const normalized = hasZone ? raw : `${raw}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Segundos transcurridos desde `since` (UTC). Nunca negativo. */
export function elapsedSecondsUtc(since, nowMs = Date.now(), fallbackSeconds = 0) {
  const start = parseUtcDate(since);
  if (start) {
    return Math.max(0, Math.floor((nowMs - start.getTime()) / 1000));
  }
  return Math.max(0, fallbackSeconds ?? 0);
}
