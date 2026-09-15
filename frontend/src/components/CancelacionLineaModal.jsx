import { useEffect, useState } from "react";
import { formatApiError } from "../utils/apiError";
import { cancelarLineaPedido, getMotivosCancelacion } from "../services/pedidosService";

export default function CancelacionLineaModal({
  linea,
  onClose,
  onOk,
}) {
  const [motivos, setMotivos] = useState([]);
  const [motivo, setMotivo] = useState("Producto duplicado");
  const [detalle, setDetalle] = useState("");
  const [modo, setModo] = useState(linea?.cantidad > 1 ? "unidad" : "todo");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    getMotivosCancelacion()
      .then((data) => setMotivos(data.motivos || []))
      .catch(() =>
        setMotivos([
          "Producto duplicado",
          "Error de captura",
          "Cambio solicitado por cliente",
          "Producto no disponible",
          "Otro",
        ])
      );
  }, []);

  if (!linea) return null;

  const cantidad = modo === "unidad" ? 1 : Number(linea.cantidad);

  const confirmar = async () => {
    if (enviando) return;
    if (motivo === "Otro" && !detalle.trim()) {
      alert("Indica el detalle del motivo");
      return;
    }
    setEnviando(true);
    try {
      const pedido = await cancelarLineaPedido(linea.id_detalle_pedido, {
        cantidad,
        motivo,
        motivo_detalle: motivo === "Otro" ? detalle : null,
        cantidad_actual: linea.cantidad,
      });
      onOk(pedido);
    } catch (err) {
      if (err.response?.status === 409) {
        onOk(null, { stale: true, message: formatApiError(err, "Actualiza el pedido") });
        return;
      }
      alert(formatApiError(err, "No se pudo cancelar la línea"));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      onClick={enviando ? undefined : onClose}
      role="presentation"
    >
      <div
        className="modal-box modal-box--cancel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="cancel-linea-title"
      >
        <h2 id="cancel-linea-title">Cancelar producto enviado</h2>
        <p>
          <strong>{linea.nombre_producto}</strong> · cantidad actual {linea.cantidad}
        </p>
        {Number(linea.cantidad) > 1 && (
          <div className="form-row" style={{ marginBottom: "0.75rem" }}>
            <label className="extra-chip">
              <input
                type="radio"
                name="cancel-modo"
                checked={modo === "unidad"}
                onChange={() => setModo("unidad")}
              />
              Disminuir una unidad
            </label>
            <label className="extra-chip">
              <input
                type="radio"
                name="cancel-modo"
                checked={modo === "todo"}
                onChange={() => setModo("todo")}
              />
              Cancelar toda la línea
            </label>
          </div>
        )}
        <label>
          Motivo
          <select
            className="select"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
          >
            {motivos.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        {motivo === "Otro" && (
          <label>
            Detalle
            <textarea
              className="input"
              rows={2}
              maxLength={300}
              value={detalle}
              onChange={(e) => setDetalle(e.target.value)}
            />
          </label>
        )}
        <div className="modal-footer">
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={enviando}>
            Volver
          </button>
          <button
            type="button"
            className="btn btn--danger"
            onClick={confirmar}
            disabled={enviando}
          >
            {enviando ? "Cancelando…" : "Confirmar cancelación"}
          </button>
        </div>
      </div>
    </div>
  );
}
