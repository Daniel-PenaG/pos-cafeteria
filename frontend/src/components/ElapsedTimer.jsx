import { useEffect, useState } from "react";
import { formatDuration } from "../utils/formatDuration";
import { elapsedSecondsUtc } from "../utils/parseUtcDate";

export default function ElapsedTimer({ since, initialSeconds, className = "" }) {
  const [secs, setSecs] = useState(() =>
    elapsedSecondsUtc(since, Date.now(), initialSeconds ?? 0)
  );

  useEffect(() => {
    const tick = () => {
      setSecs(elapsedSecondsUtc(since, Date.now(), initialSeconds ?? 0));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
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
