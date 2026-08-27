import { useEffect, useState } from "react";
import { generateQrDataUrl } from "../utils/fidelidadQr";

export default function QrCodeDisplay({ codigo, size = 220, showCode = true }) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    if (!codigo) {
      setSrc("");
      return;
    }
    let cancelled = false;
    generateQrDataUrl(codigo, size).then((url) => {
      if (!cancelled) setSrc(url);
    });
    return () => {
      cancelled = true;
    };
  }, [codigo, size]);

  if (!codigo) return null;
  if (!src) return <p className="hint">Generando código QR…</p>;

  return (
    <div style={{ textAlign: "center" }}>
      <img
        src={src}
        alt={`QR ${codigo}`}
        width={size}
        height={size}
        style={{ display: "block", margin: "0 auto", borderRadius: 8 }}
      />
      {showCode && (
        <p style={{ marginTop: "0.75rem", marginBottom: 0 }}>
          <code>{codigo}</code>
        </p>
      )}
    </div>
  );
}
