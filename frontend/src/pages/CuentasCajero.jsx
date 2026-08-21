import { useCallback, useEffect, useState } from "react";
import { HiOutlineArrowPath, HiOutlineUserCircle } from "react-icons/hi2";
import PageHeader from "../components/PageHeader";
import { getCuentasPorCajero } from "../services/reportesService";
import { fechaMexicoISO, formatearHoraMexico } from "../utils/datetimeMx";

function formatearHora(iso) {
  return formatearHoraMexico(iso);
}

function formatearFormaPago(forma) {
  const map = {
    EFECTIVO: "Efectivo",
    TARJETA: "Tarjeta",
    TRANSFERENCIA: "Transferencia",
  };
  return map[forma] || forma;
}

export default function CuentasCajero() {
  const hoy = fechaMexicoISO();
  const [fecha, setFecha] = useState(hoy);
  const [reporte, setReporte] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ultimaActualizacion, setUltimaActualizacion] = useState(null);

  const esHoy = fecha === hoy;

  const cargar = useCallback(async () => {
    if (!fecha) return;
    setLoading(true);
    try {
      const data = await getCuentasPorCajero(fecha);
      setReporte(data);
      setUltimaActualizacion(new Date());
    } catch (err) {
      alert(err.response?.data?.detail || "Error al cargar cuentas por cajero");
    } finally {
      setLoading(false);
    }
  }, [fecha]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  useEffect(() => {
    if (!esHoy) return;

    const interval = setInterval(() => {
      const diaActual = fechaMexicoISO();
      if (diaActual !== fecha) {
        setFecha(diaActual);
        return;
      }
      cargar();
    }, 60000);

    const onVisible = () => {
      if (document.visibilityState === "visible") {
        const diaActual = fechaMexicoISO();
        if (diaActual !== fecha) {
          setFecha(diaActual);
        } else {
          cargar();
        }
      }
    };

    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [esHoy, fecha, cargar]);

  return (
    <div className="page page--cuentas-cajero">
      <PageHeader
        title="Cuentas por cajero"
        subtitle="Ventas del día agrupadas por quien cobró cada cuenta"
      />

      <div className="card cuentas-cajero__controls">
        <div className="cuentas-cajero__controls-row">
          <div className="form-row" style={{ marginBottom: 0 }}>
            <label htmlFor="fecha-cajero">Fecha</label>
            <input
              id="fecha-cajero"
              type="date"
              className="input"
              value={fecha}
              max={hoy}
              onChange={(e) => setFecha(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn btn--accent inline-flex items-center gap-2"
            onClick={cargar}
            disabled={loading}
          >
            <HiOutlineArrowPath className={`size-5 ${loading ? "animate-spin" : ""}`} aria-hidden />
            {loading ? "Actualizando…" : "Actualizar"}
          </button>
        </div>
        <p className="hint cuentas-cajero__hint">
          {esHoy
            ? "Vista del día en curso: se actualiza sola cada minuto y al volver a esta pestaña."
            : "Consulta histórica del día seleccionado."}
          {ultimaActualizacion && (
            <>
              {" "}
              Última actualización:{" "}
              {ultimaActualizacion.toLocaleTimeString("es-MX", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </>
          )}
        </p>
      </div>

      {reporte && (
        <>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card">
              <p className="stat-card__label">Total del día</p>
              <p className="stat-card__value">${Number(reporte.total_dia).toFixed(2)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Cuentas cobradas</p>
              <p className="stat-card__value">{reporte.numero_ventas}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Personas activas</p>
              <p className="stat-card__value">{reporte.numero_cajeros}</p>
            </div>
          </div>

          {reporte.por_cajero.length === 0 ? (
            <p className="empty-state">No hay cuentas cobradas en esta fecha.</p>
          ) : (
            <>
              <div className="card" style={{ marginBottom: "1.5rem" }}>
                <h3>Resumen por persona</h3>
                <table className="table" style={{ marginTop: "0.75rem" }}>
                  <thead>
                    <tr>
                      <th>Persona</th>
                      <th>Rol</th>
                      <th>Cuentas</th>
                      <th>Total</th>
                      <th>% del día</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reporte.por_cajero.map((c) => (
                      <tr key={c.id_usuario}>
                        <td>
                          <strong>{c.nombre}</strong>
                          <span className="hint" style={{ marginLeft: "0.35rem" }}>
                            @{c.usuario_login}
                          </span>
                        </td>
                        <td>{c.rol}</td>
                        <td>{c.numero_ventas}</td>
                        <td>${Number(c.total).toFixed(2)}</td>
                        <td>{c.porcentaje_dia}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {reporte.por_cajero.map((c) => (
                <div key={c.id_usuario} className="card cuentas-cajero__persona">
                  <div className="cuentas-cajero__persona-head">
                    <h3 className="inline-flex items-center gap-2">
                      <HiOutlineUserCircle className="size-6 text-olive shrink-0" aria-hidden />
                      {c.nombre}
                    </h3>
                    <span className="cuentas-cajero__persona-meta">
                      {c.numero_ventas} cuenta{c.numero_ventas !== 1 ? "s" : ""} · $
                      {Number(c.total).toFixed(2)} · {c.porcentaje_dia}% del día
                    </span>
                  </div>

                  <table className="table" style={{ marginTop: "0.75rem" }}>
                    <thead>
                      <tr>
                        <th>Folio</th>
                        <th>Hora</th>
                        <th>Origen</th>
                        <th>Pago</th>
                        <th>Cliente</th>
                        <th>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {c.ventas.map((v) => (
                        <tr key={v.id_venta}>
                          <td>#{v.id_venta}</td>
                          <td>{formatearHora(v.fecha_hora)}</td>
                          <td>
                            {v.mesa_label}
                            {v.para_llevar && (
                              <span className="badge" style={{ marginLeft: "0.35rem" }}>
                                llevar
                              </span>
                            )}
                          </td>
                          <td>{formatearFormaPago(v.forma_pago)}</td>
                          <td>
                            {v.cliente_nombre || "—"}
                            {v.puntos_generados > 0 && (
                              <span className="hint" style={{ marginLeft: "0.25rem" }}>
                                (+{v.puntos_generados} pts)
                              </span>
                            )}
                          </td>
                          <td>${Number(v.total).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}
