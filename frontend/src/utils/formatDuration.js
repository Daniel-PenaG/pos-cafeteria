/** Formatea segundos a texto legible (comandera / timers). */
export function formatDuration(segundos) {
  if (segundos == null || segundos < 0) return "—";
  const m = Math.floor(segundos / 60);
  const s = segundos % 60;
  const h = Math.floor(m / 60);
  const mins = m % 60;
  if (h > 0) return `${h}h ${mins}m ${s}s`;
  if (mins > 0) return `${mins}m ${String(s).padStart(2, "0")}s`;
  return `${s}s`;
}
