/** Mensaje legible desde errores de Axios / FastAPI */
export function formatApiError(err, fallback = "Error de conexión") {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((x) => x?.msg).filter(Boolean);
    if (msgs.length) return msgs.join(", ");
  }
  if (err?.response?.status) {
    return `${fallback} (HTTP ${err.response.status})`;
  }
  if (err?.message) return err.message;
  return fallback;
}
