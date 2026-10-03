import { useEffect, useMemo, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { getResumenDashboard } from "../services/dashboardService";
import { createGasto, deleteGasto, getGastos } from "../services/gastosService";
import { getCuentasTesoreria, getEstadoTesoreria } from "../services/tesoreriaService";

import { fechaMexicoISO, formatearHoraMexico } from "../utils/datetimeMx";

function formatearHora(iso) {
  return formatearHoraMexico(iso);
}

export default function Gastos() {
  const [fecha, setFecha] = useState(() => fechaMexicoISO());
  const [gastos, setGastos] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [descripcion, setDescripcion] = useState("");
  const [monto, setMonto] = useState("");
  const [loading, setLoading] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [tesoreriaActiva, setTesoreriaActiva] = useState(false);
  const [cuentas, setCuentas] = useState([]);
  const [codigoCuenta, setCodigoCuenta] = useState("");
  const [clasificacion, setClasificacion] = useState("GASTO_OPERATIVO");
  const [estadoPago, setEstadoPago] = useState("PAGADO");

  const totalGastos = useMemo(
    () => gastos.reduce((acc, g) => acc + Number(g.monto), 0),
    [gastos]
  );

  const cargar = useCallback(async () => {
    try {
      setLoading(true);
      const [lista, dash] = await Promise.all([
        getGastos(fecha),
        getResumenDashboard(fecha),
      ]);
      setGastos(lista);
      setResumen(dash);
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Error al cargar gastos");
    } finally {
      setLoading(false);
    }
  }, [fecha]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  useEffect(() => {
    getEstadoTesoreria()
      .then(async (estado) => {
        setTesoreriaActiva(Boolean(estado?.activa));
        if (estado?.activa) {
          const lista = await getCuentasTesoreria();
          setCuentas(lista || []);
          if (lista?.[0]?.codigo) setCodigoCuenta(lista[0].codigo);
        }
      })
      .catch(() => setTesoreriaActiva(false));
  }, []);

  const registrar = async (e) => {
    e.preventDefault();
    const m = parseFloat(monto);
    if (!descripcion.trim()) {
      alert("Escribe la descripción del gasto");
      return;
    }
    if (!monto || isNaN(m) || m <= 0) {
      alert("Indica un monto mayor a 0");
      return;
    }
    if (tesoreriaActiva && estadoPago === "PAGADO" && !codigoCuenta) {
      alert("Elige la cuenta desde la que se paga");
      return;
    }
    try {
      setGuardando(true);
      const payload = { descripcion: descripcion.trim(), monto: m };
      if (tesoreriaActiva) {
        payload.estado_pago = estadoPago;
        payload.clasificacion = clasificacion;
        if (estadoPago === "PAGADO") payload.codigo_cuenta = codigoCuenta;
      }
      await createGasto(payload);
      setDescripcion("");
      setMonto("");
      await cargar();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al registrar gasto");
    } finally {
      setGuardando(false);
    }
  };

  const eliminar = async (gasto) => {
    if (!window.confirm(`¿Eliminar gasto "${gasto.descripcion}"?`)) return;
    try {
      await deleteGasto(gasto.id_gasto);
      await cargar();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar");
    }
  };

  const capitalNeto = resumen?.capital_neto_hoy ?? null;
  const ventasHoy = resumen?.total_hoy ?? 0;

  return (
    <div className="page">
      <PageHeader
        title="Gastos del día"
        subtitle="Registra compras y egresos en efectivo — se descuentan del capital neto del día"
      />

      <div className="stat-grid" style={{ marginBottom: "1.5rem" }}>
        <div className="stat-card">
          <div className="stat-card__label">Ventas del día</div>
          <div className="stat-card__value">${ventasHoy.toFixed(2)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Gastos del día</div>
          <div className="stat-card__value" style={{ color: "var(--berry)" }}>
            −${totalGastos.toFixed(2)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Capital neto</div>
          <div className="stat-card__value" style={{ color: "var(--olive)" }}>
            ${capitalNeto != null ? capitalNeto.toFixed(2) : "—"}
          </div>
        </div>
      </div>

      <section className="card" style={{ marginBottom: "1.5rem" }}>
        <div className="form-row" style={{ maxWidth: 220 }}>
          <label htmlFor="fecha-gastos">Fecha</label>
          <input
            id="fecha-gastos"
            type="date"
            className="input"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
          />
        </div>

        <form onSubmit={registrar} className="form-grid" style={{ marginTop: "1rem" }}>
          <div className="form-row">
            <label htmlFor="gasto-desc">Compra / concepto *</label>
            <input
              id="gasto-desc"
              className="input"
              value={descripcion}
              onChange={(e) => setDescripcion(e.target.value)}
              placeholder="Ej. Leche, servilletas, gasolina…"
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="gasto-monto">Monto *</label>
            <input
              id="gasto-monto"
              type="number"
              className="input"
              min="0.01"
              step="0.01"
              value={monto}
              onChange={(e) => setMonto(e.target.value)}
              placeholder="Ej. 150.00"
              required
            />
          </div>
          {tesoreriaActiva && (
            <>
              <div className="form-row">
                <label htmlFor="gasto-clase">Clasificación</label>
                <select id="gasto-clase" className="input" value={clasificacion} onChange={(e) => setClasificacion(e.target.value)}>
                  <option value="GASTO_OPERATIVO">Gasto operativo</option>
                  <option value="RETIRO_PROPIETARIO">Retiro del propietario</option>
                </select>
              </div>
              <div className="form-row">
                <label htmlFor="gasto-estado">Pago</label>
                <select id="gasto-estado" className="input" value={estadoPago} onChange={(e) => setEstadoPago(e.target.value)}>
                  <option value="PAGADO">Pagado</option>
                  <option value="PENDIENTE">Pendiente</option>
                </select>
              </div>
              {estadoPago === "PAGADO" && (
                <div className="form-row">
                  <label htmlFor="gasto-cuenta">Cuenta</label>
                  <select id="gasto-cuenta" className="input" value={codigoCuenta} onChange={(e) => setCodigoCuenta(e.target.value)}>
                    {cuentas.map((cuenta) => (
                      <option key={cuenta.codigo} value={cuenta.codigo}>{cuenta.nombre}</option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}
          <div className="form-row" style={{ alignSelf: "end" }}>
            <button type="submit" className="btn btn--primary" disabled={guardando}>
              {guardando ? "Guardando…" : "Registrar gasto"}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <div className="table-toolbar">
          <h2 style={{ margin: 0 }}>Gastos registrados</h2>
          <span className="hint">{gastos.length} registro(s)</span>
        </div>

        {loading ? (
          <p className="loading-state">Cargando…</p>
        ) : gastos.length === 0 ? (
          <p className="empty-state">No hay gastos en esta fecha.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Hora</th>
                  <th>Concepto</th>
                  <th>Registró</th>
                  <th>Monto</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {gastos.map((g) => (
                  <tr key={g.id_gasto}>
                    <td>{formatearHora(g.fecha_hora)}</td>
                    <td>{g.descripcion}</td>
                    <td>{g.usuario_nombre || "—"}</td>
                    <td>${Number(g.monto).toFixed(2)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--danger btn--sm"
                        onClick={() => eliminar(g)}
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="hint" style={{ marginTop: "1rem", marginBottom: 0 }}>
          El capital neto también aparece en el{" "}
          <Link to="/dashboard">Dashboard</Link> (ventas − gastos del día).
        </p>
      </section>
    </div>
  );
}
