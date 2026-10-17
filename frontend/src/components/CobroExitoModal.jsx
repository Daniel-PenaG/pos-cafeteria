import { useLayoutEffect } from "react";
import { appendInventarioAMensajeCobro, buildResumenInventarioCobro } from "../utils/cobroAdvertencias";
import { formatDuration } from "../utils/formatDuration";

/**
 * Resumen post-cobro en UI (sustituye alert() bloqueante).
 */
export default function CobroExitoModal({ open, resumen, onClose, onImprimirTicket }) {
  useLayoutEffect(() => {
    if (!open && import.meta.env.MODE === "e2e") {
      window.__posE2e?.markCobroClose?.("modal_hidden");
    }
  }, [open]);

  if (!open || !resumen) return null;

  const {
    venta,
    modoParaLlevar,
    numeroMesa,
    segundosEnMesa,
    pagaCon,
    cambio,
    printHint,
    clienteNombre,
  } = resumen;

  const avisos = resumen.advertenciasInventario || [];
  let cuerpo = modoParaLlevar
    ? `Venta para llevar — Folio: ${venta.id_venta}\nTotal: $${Number(venta.total).toFixed(2)}`
    : `Cuenta cerrada. Mesa ${venta.numero_mesa ?? numeroMesa} — Folio: ${venta.id_venta}\nTotal: $${Number(venta.total).toFixed(2)}`;

  if (!modoParaLlevar && segundosEnMesa != null) {
    cuerpo += `\n\nTiempo en mesa: ${formatDuration(segundosEnMesa)}`;
  }
  if (pagaCon != null && cambio != null) {
    cuerpo += `\n\nPaga con: $${Number(pagaCon).toFixed(2)}\nCambio: $${Number(cambio).toFixed(2)}`;
  }
  cuerpo = appendInventarioAMensajeCobro(cuerpo, avisos);
  if (venta.saldo_anterior != null) {
    cuerpo += `\n\nSaldo anterior: ${venta.saldo_anterior}`;
    cuerpo += `\nPuntos usados: ${venta.puntos_canje || 0}`;
    cuerpo += `\nPuntos generados: ${venta.puntos_generados || 0}`;
    cuerpo += `\nSaldo final: ${venta.saldo_final}`;
  }
  if (clienteNombre) {
    cuerpo = `Cliente: ${clienteNombre}\n\n${cuerpo}`;
  }
  if (printHint) {
    cuerpo += `\n\n${printHint}`;
  }

  const resumenInv = buildResumenInventarioCobro(avisos);

  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div
        className="modal-box modal-box--cobro-exito"
        data-nav-cobro-resumen="visible"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="cobro-exito-title"
      >
        <h2 id="cobro-exito-title">Cobro registrado</h2>
        <pre className="cobro-exito__body">{cuerpo}</pre>
        {resumenInv.esResumido && (
          <p className="hint cobro-exito__inv-hint">{resumenInv.texto}</p>
        )}
        <div className="btn-group" style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {onImprimirTicket ? (
            <button type="button" className="btn btn--secondary" onClick={onImprimirTicket}>
              Reimprimir ticket
            </button>
          ) : null}
          <button type="button" className="btn btn--accent" style={{ flex: 1 }} onClick={onClose} autoFocus>
            Continuar
          </button>
        </div>
      </div>
    </div>
  );
}
