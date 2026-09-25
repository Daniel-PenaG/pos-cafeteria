import { useCallback, useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import {
  anularSesionCaja,
  listarSesionesCaja,
  revisarSesionCaja,
} from "../services/cajaService";
import { getCierresDia as getCierresHistoricos } from "../services/cierresService";
import { fechaMexicoISO, formatearHoraMexico } from "../utils/datetimeMx";
import { formatApiError } from "../utils/apiError";
import { etiquetaEstadoCaja, fmtCaja } from "../utils/cajaArqueo.js";
import { useAuthStore } from "../store/authStore";
import { hasAction } from "../config/permissions";

export default function CierresDia() {
  const user = useAuthStore((s) => s.user);
  const [estado, setEstado] = useState("");
  const [sesiones, setSesiones] = useState([]);
  const [historicos, setHistoricos] = useState([]);
  const [fecha, setFecha] = useState(fechaMexicoISO());
  const [loading, setLoading] = useState(true);
  const [detalle, setDetalle] = useState(null);
  const [motivoAnula, setMotivoAnula] = useState("");

  const puedeRevisar = hasAction(user?.rol, "REVISAR_CIERRE_CAJA", user?.permisos_acciones);
  const puedeAnular = hasAction(user?.rol, "ANULAR_CIERRE_CAJA", user?.permisos_acciones);

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (estado) params.estado = estado;
      const [lista, hist] = await Promise.all([
        listarSesionesCaja(params),
        getCierresHistoricos(fecha).catch(() => []),
      ]);
      setSesiones(Array.isArray(lista) ? lista : []);
      setHistoricos(Array.isArray(hist) ? hist : []);
    } catch (err) {
      alert(formatApiError(err, "Error al cargar sesiones"));
    } finally {
      setLoading(false);
    }
  }, [estado, fecha]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const handleRevisar = async (id) => {
    try {
      await revisarSesionCaja(id);
      await cargar();
    } catch (err) {
      alert(formatApiError(err, "No se pudo revisar"));
    }
  };

  const handleAnular = async (id) => {
    if (!motivoAnula.trim()) {
      alert("Indica el motivo de anulación");
      return;
    }
    try {
      await anularSesionCaja(id, motivoAnula.trim());
      setMotivoAnula("");
      await cargar();
    } catch (err) {
      alert(formatApiError(err, "No se pudo anular"));
    }
  };

  const pendientes = sesiones.filter((s) => s.estado === "CERRADA_CON_DIFERENCIA");

  return (
    <div className="caja-page">
      <PageHeader
        title="Cierres del día"
        subtitle="Sesiones de caja, diferencias pendientes y revisión administrativa"
      />

      <div className="card caja-card caja-admin-filters">
        <div className="form-row">
          <label htmlFor="filtro-estado">Estado</label>
          <select id="filtro-estado" className="select" value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="">Todos</option>
            <option value="ABIERTA">Abierta</option>
            <option value="EN_ARQUEO">En arqueo</option>
            <option value="CERRADA_CONCILIADA">Conciliada</option>
            <option value="CERRADA_CON_DIFERENCIA">Con diferencia</option>
            <option value="REVISADA">Revisada</option>
            <option value="ANULADA">Anulada</option>
          </select>
        </div>
        <div className="form-row">
          <label htmlFor="fecha-hist">Histórico por fecha</label>
          <input
            id="fecha-hist"
            type="date"
            className="input"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
          />
        </div>
      </div>

      {pendientes.length > 0 && (
        <p className="hint caja-banner">
          {pendientes.length} cierre(s) con diferencia pendientes de revisión.
        </p>
      )}

      {loading ? (
        <p>Cargando…</p>
      ) : (
        <div className="table-wrap card">
          <table>
            <thead>
              <tr>
                <th>Cajero</th>
                <th>Terminal</th>
                <th>Estado</th>
                <th>Apertura</th>
                <th>Cierre</th>
                <th>Dif. efectivo</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sesiones.map((s) => (
                <tr key={s.id_sesion_caja}>
                  <td>{s.usuario_nombre || s.id_usuario}</td>
                  <td>{s.terminal}</td>
                  <td>{etiquetaEstadoCaja(s.estado)}</td>
                  <td>{formatearHoraMexico(s.fecha_apertura)}</td>
                  <td>{s.fecha_cierre ? formatearHoraMexico(s.fecha_cierre) : "—"}</td>
                  <td>{s.diferencia_efectivo != null ? fmtCaja(s.diferencia_efectivo) : "—"}</td>
                  <td>
                    <div className="caja-admin-actions">
                      <button type="button" className="btn btn--ghost" onClick={() => setDetalle(s)}>
                        Ver
                      </button>
                      {puedeRevisar && ["CERRADA_CONCILIADA", "CERRADA_CON_DIFERENCIA"].includes(s.estado) && (
                        <button type="button" className="btn btn--secondary" onClick={() => handleRevisar(s.id_sesion_caja)}>
                          Revisar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {sesiones.length === 0 && <p className="empty-state">Sin sesiones con ese filtro.</p>}
        </div>
      )}

      {detalle && (
        <div className="card caja-card">
          <h3>Sesión #{detalle.id_sesion_caja}</h3>
          <p className="hint">
            {etiquetaEstadoCaja(detalle.estado)} · {detalle.terminal} · {detalle.usuario_nombre}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Método</th>
                  <th>Esperado</th>
                  <th>Declarado</th>
                  <th>Diferencia</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Efectivo</td>
                  <td>{fmtCaja(detalle.esperado_efectivo)}</td>
                  <td>{fmtCaja(detalle.declarado_efectivo)}</td>
                  <td>{fmtCaja(detalle.diferencia_efectivo)}</td>
                </tr>
                <tr>
                  <td>Transferencia</td>
                  <td>{fmtCaja(detalle.esperado_transferencia)}</td>
                  <td>{fmtCaja(detalle.declarado_transferencia)}</td>
                  <td>{fmtCaja(detalle.diferencia_transferencia)}</td>
                </tr>
                <tr>
                  <td>Terminal</td>
                  <td>{fmtCaja(detalle.esperado_tarjeta)}</td>
                  <td>{fmtCaja(detalle.declarado_tarjeta)}</td>
                  <td>{fmtCaja(detalle.diferencia_tarjeta)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          {detalle.observacion_cierre && <p className="hint">Obs.: {detalle.observacion_cierre}</p>}
          {detalle.motivo_anulacion && <p className="hint">Anulación: {detalle.motivo_anulacion}</p>}
          {puedeAnular && detalle.estado !== "ANULADA" && (
            <div className="form-row">
              <label htmlFor="motivo-anula">Motivo de anulación</label>
              <input
                id="motivo-anula"
                className="input"
                value={motivoAnula}
                onChange={(e) => setMotivoAnula(e.target.value)}
              />
              <button type="button" className="btn btn--danger" onClick={() => handleAnular(detalle.id_sesion_caja)}>
                Anular
              </button>
            </div>
          )}
          <button type="button" className="btn btn--ghost" onClick={() => setDetalle(null)}>
            Cerrar detalle
          </button>
        </div>
      )}

      <div className="card caja-card">
        <h3>Cierres históricos del {fecha}</h3>
        {historicos.length === 0 ? (
          <p className="empty-state">Sin snapshots diarios en esa fecha.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Ventas</th>
                  <th>Efectivo</th>
                  <th>Diferencia</th>
                </tr>
              </thead>
              <tbody>
                {historicos.map((c) => (
                  <tr key={c.id_cierre}>
                    <td>{c.usuario_nombre || c.id_usuario}</td>
                    <td>{fmtCaja(c.total_ventas)}</td>
                    <td>{fmtCaja(c.total_efectivo)}</td>
                    <td>{fmtCaja(c.diferencia)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
