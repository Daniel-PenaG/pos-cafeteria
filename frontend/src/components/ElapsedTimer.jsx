import { useEffect, useState } from "react";

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

export default function ElapsedTimer({ since, initialSeconds, className = "" }) {
  const [secs, setSecs] = useState(initialSeconds ?? 0);

  useEffect(() => {
    if (since) {
      const start = new Date(since).getTime();
      const tick = () => setSecs(Math.max(0, Math.floor((Date.now() - start) / 1000)));
      tick();
      const id = setInterval(tick, 1000);
      return () => clearInterval(id);
    }
    if (initialSeconds != null) {
      setSecs(initialSeconds);
    }
  }, [since, initialSeconds]);

  let urgency = "";
  if (secs >= 900) urgency = "comandera-timer--critical";
  else if (secs >= 600) urgency = "comandera-timer--warning";

  return (
    <span className={`comandera-timer ${urgency} ${className}`.trim()} title="Tiempo en preparación">
      ⏱ {formatDuration(secs)}
    </span>
  );
}
