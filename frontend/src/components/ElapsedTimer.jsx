import { useEffect, useState } from "react";
import { formatDuration } from "../utils/formatDuration";

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
