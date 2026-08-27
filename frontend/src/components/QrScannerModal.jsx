import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { parseCodigoFidelidad } from "../utils/fidelidadQr";

const SCANNER_ID = "fidelidad-qr-scanner";

export default function QrScannerModal({ open, onClose, onScan }) {
  const scannerRef = useRef(null);
  const [error, setError] = useState("");
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    if (!open) return undefined;

    let cancelled = false;
    const html5 = new Html5Qrcode(SCANNER_ID);
    scannerRef.current = html5;
    setError("");
    setScanning(false);

    const stopScanner = async () => {
      try {
        if (html5.isScanning) await html5.stop();
      } catch {
        /* ignore */
      }
    };

    Html5Qrcode.getCameras()
      .then((cameras) => {
        if (cancelled) return null;
        if (!cameras?.length) throw new Error("No se encontró cámara en este dispositivo");
        const cam = cameras.find((c) => /back|rear|trase/i.test(c.label)) || cameras[cameras.length - 1];
        return html5.start(
          cam.id,
          { fps: 10, qrbox: { width: 260, height: 260 }, aspectRatio: 1 },
          (decoded) => {
            const codigo = parseCodigoFidelidad(decoded);
            if (!codigo) return;
            stopScanner().then(() => {
              if (!cancelled) onScan(codigo);
            });
          },
          () => {}
        );
      })
      .then(() => {
        if (!cancelled) setScanning(true);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.message || "No se pudo abrir la cámara. Revisa permisos.");
        }
      });

    return () => {
      cancelled = true;
      stopScanner();
      scannerRef.current = null;
    };
  }, [open, onScan]);

  if (!open) return null;

  return (
    <div className="modal-overlay" style={{ zIndex: 1200 }} onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <h2>Escanear QR del cliente</h2>
        <p className="hint" style={{ marginBottom: "0.75rem" }}>
          Apunta al código QR del cliente (CAFE-…)
        </p>
        <div
          id={SCANNER_ID}
          style={{
            width: "100%",
            minHeight: 280,
            overflow: "hidden",
            borderRadius: 8,
            background: "#111",
          }}
        />
        {!scanning && !error && <p className="hint">Iniciando cámara…</p>}
        {error && <p className="hint" style={{ color: "var(--danger, #c0392b)" }}>{error}</p>}
        <div className="modal-footer">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
