import { useEffect, useState } from "react";
import { HiOutlinePrinter } from "react-icons/hi2";
import {
  canUseBluetoothPrinter,
  listBluetoothPrinters,
  printEscPosBytes,
} from "../services/printerService";
import {
  getSavedPrinter,
  savePrinter,
  clearSavedPrinter,
} from "../services/printerStorage";
import { buildTestTicket } from "../services/escposTickets";

export default function PrinterSettings({ open, onClose }) {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(() => getSavedPrinter());
  const [error, setError] = useState("");

  const refreshDevices = async () => {
    if (!canUseBluetoothPrinter()) return;
    setLoading(true);
    setError("");
    try {
      const list = await listBluetoothPrinters();
      setDevices(list);
      if (list.length === 0) {
        setError(
          "No hay impresoras emparejadas. Empareja la MHT-P58D en Ajustes → Bluetooth de la tablet."
        );
      }
    } catch (err) {
      setError(err?.message || "Error al buscar impresoras");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    setSaved(getSavedPrinter());
    refreshDevices();
  }, [open]);

  if (!open) return null;

  if (!canUseBluetoothPrinter()) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-box" onClick={(e) => e.stopPropagation()}>
          <h2>Impresora</h2>
          <p className="hint">
            La impresión Bluetooth solo funciona en la <strong>app Android</strong> instalada
            en la tablet. La versión web de Amplify no imprime directo.
          </p>
          <div className="modal-footer">
            <button type="button" className="btn btn--secondary" onClick={onClose}>
              Cerrar
            </button>
          </div>
        </div>
      </div>
    );
  }

  const seleccionar = (device) => {
    savePrinter(device);
    setSaved(getSavedPrinter());
  };

  const probar = async () => {
    try {
      setLoading(true);
      await printEscPosBytes(buildTestTicket());
      alert("Ticket de prueba enviado.");
    } catch (err) {
      alert(err?.message || "Error al imprimir prueba");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <h2 className="flex items-center gap-2">
          <HiOutlinePrinter className="size-6 text-olive" aria-hidden />
          Impresora Bluetooth
        </h2>
        <p className="hint">
          Empareja la <strong>MHT-P58D</strong> en Ajustes del sistema, luego elígela aquí.
        </p>

        {saved && (
          <div className="panel-muted" style={{ marginBottom: "1rem" }}>
            <strong>Activa:</strong> {saved.name}
            <span className="hint" style={{ marginLeft: "0.35rem" }}>
              ({saved.address})
            </span>
          </div>
        )}

        {error && (
          <p className="hint" style={{ color: "var(--berry)" }}>
            {error}
          </p>
        )}

        <div className="btn-group" style={{ marginBottom: "1rem" }}>
          <button
            type="button"
            className="btn btn--secondary btn--sm"
            onClick={refreshDevices}
            disabled={loading}
          >
            {loading ? "Buscando…" : "Actualizar lista"}
          </button>
          {saved && (
            <>
              <button
                type="button"
                className="btn btn--accent btn--sm"
                onClick={probar}
                disabled={loading}
              >
                Imprimir prueba
              </button>
              <button
                type="button"
                className="btn btn--danger btn--sm"
                onClick={() => {
                  clearSavedPrinter();
                  setSaved(null);
                }}
              >
                Quitar
              </button>
            </>
          )}
        </div>

        {devices.length > 0 && (
          <ul className="extras-asignados-list">
            {devices.map((d) => (
              <li key={d.address} className="extra-asignado-item">
                <span>
                  {d.name}
                  <span className="hint" style={{ marginLeft: "0.35rem" }}>
                    {d.address}
                  </span>
                </span>
                <button
                  type="button"
                  className={`btn btn--sm ${saved?.address === d.address ? "btn--accent" : "btn--secondary"}`}
                  onClick={() => seleccionar(d)}
                >
                  {saved?.address === d.address ? "Seleccionada" : "Usar"}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="modal-footer">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
