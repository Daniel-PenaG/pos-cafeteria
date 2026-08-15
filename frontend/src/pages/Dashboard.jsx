import { useEffect, useState } from "react";
import { getResumenDashboard } from "../services/dashboardService";
import { getConfiguracion, updateConfiguracion } from "../services/configuracionService";
import PageHeader from "../components/PageHeader";
import { useAuthStore } from "../store/authStore";
import { isAdmin } from "../config/permissions";

function fechaLocalISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatearHora(iso) {
  return new Date(iso).toLocaleTimeString("es-MX", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatearFormaPago(forma) {
  const map = {
    EFECTIVO: "Efectivo",
    TARJETA: "Tarjeta",
    TRANSFERENCIA: "Transferencia",
  };
  return map[forma] || forma;
}

export default function Dashboard() {
  const rol = useAuthStore((state) => state.user?.rol);
  const admin = isAdmin(rol);
  const [data, setData] = useState(null);
  const [config, setConfig] = useState(null);
  const [editing, setEditing] = useState(false);
  const [margenEditado, setMargenEditado] = useState("");
  const [gastosEditados, setGastosEditados] = useState("");
  const [fechaConsulta, setFechaConsulta] = useState(fechaLocalISO());

  const cargarDashboard = async () => {
    const hoy = fechaLocalISO();
    try {
      const resumenData = await getResumenDashboard(hoy);
      setData(resumenData);
      setFechaConsulta(resumenData.hoy || hoy);

      if (admin) {
        const configData = await getConfiguracion();
        setConfig(configData);
        setMargenEditado(configData.margen_ganancia);
        setGastosEditados(configData.gastos_fijos);
      }
    } catch (err) {
      console.error(err);
      alert("Error al cargar el dashboard");
    }
  };

  useEffect(() => {
    cargarDashboard();

    const interval = setInterval(() => {
      const hoy = fechaLocalISO();
      if (hoy !== fechaConsulta) {
        cargarDashboard();
      }
    }, 60000);

    const onVisible = () => {
      if (document.visibilityState === "visible") {
        cargarDashboard();
      }
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [admin, fechaConsulta]);

  const handleGuardarConfiguracion = async () => {
    if (margenEditado < 0 || margenEditado > 100) {
      alert("El margen debe estar entre 0 y 100");
      return;
    }
    if (gastosEditados < 0) {
      alert("Los gastos fijos no pueden ser negativos");
      return;
    }

    try {
      const updated = await updateConfiguracion({
        margen_ganancia: parseFloat(margenEditado),
        gastos_fijos: parseFloat(gastosEditados),
      });
      setConfig(updated);
      setEditing(false);
      const n = updated.productos_precio_actualizados ?? 0;
      alert(
        n > 0
          ? `Configuración guardada. Se actualizaron los precios de ${n} producto(s) con receta activa.`
          : "Configuración guardada. No hay productos con receta activa para recalcular precios."
      );
    } catch (err) {
      console.error(err);
      alert("Error al actualizar la configuración");
    }
  };

  if (!data || (admin && !config)) {
    return <div className="loading-state">Cargando dashboard…</div>;
  }

  return (
    <div className="page">
      <PageHeader
        title="Dashboard"
        subtitle={`Resumen del ${fechaConsulta} — ventas de hoy y del día`}
      />

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-card__label">Ventas hoy ($)</div>
          <div className="stat-card__value">${data.total_hoy.toFixed(2)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Cuentas de hoy</div>
          <div className="stat-card__value">{data.num_ventas_hoy}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Tiempo prom. comanda</div>
          <div className="stat-card__value">{data.comanda_promedio_texto || "0s"}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Acumulado</div>
          <div className="stat-card__value">${data.total_general.toFixed(2)}</div>
        </div>
      </div>

      <section className="card" style={{ marginBottom: "1.5rem" }}>
        <h2>Cuentas de hoy</h2>
        <p className="hint" style={{ marginTop: "0.35rem" }}>
          Cada fila es una cuenta cobrada. El tiempo de comanda va desde que se envía a cocina hasta
          que todas las líneas quedan listas.
        </p>
        {!data.cuentas_hoy?.length ? (
          <p className="empty-state">No hay cuentas cobradas hoy.</p>
        ) : (
          <div className="table-wrap" style={{ marginTop: "0.75rem" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Folio</th>
                  <th>Hora</th>
                  <th>Origen</th>
                  {admin && <th>Cajero</th>}
                  <th>Pago</th>
                  <th>Comanda</th>
                  <th>Inicio</th>
                  <th>Fin</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {data.cuentas_hoy.map((c) => (
                  <tr key={c.id_venta}>
                    <td>#{c.id_venta}</td>
                    <td>{formatearHora(c.fecha_hora)}</td>
                    <td>
                      {c.mesa_label}
                      {c.para_llevar && (
                        <span className="badge" style={{ marginLeft: "0.35rem" }}>
                          llevar
                        </span>
                      )}
                    </td>
                    {admin && (
                      <td>
                        {c.cajero_nombre}
                        <span className="hint" style={{ marginLeft: "0.25rem" }}>
                          @{c.cajero_login}
                        </span>
                      </td>
                    )}
                    <td>{formatearFormaPago(c.forma_pago)}</td>
                    <td>
                      <span
                        className={
                          c.comanda_estado === "completada"
                            ? "badge badge--ok"
                            : c.comanda_estado === "en_preparacion"
                              ? "badge badge--kitchen"
                              : ""
                        }
                      >
                        {c.comanda_texto}
                      </span>
                    </td>
                    <td>{c.comanda_inicio ? formatearHora(c.comanda_inicio) : "—"}</td>
                    <td>{c.comanda_fin ? formatearHora(c.comanda_fin) : "—"}</td>
                    <td>${Number(c.total).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data.comanda_completadas_hoy > 0 && (
          <p className="hint" style={{ marginTop: "0.75rem", marginBottom: 0 }}>
            {data.comanda_completadas_hoy} cuenta
            {data.comanda_completadas_hoy !== 1 ? "s" : ""} con comanda completada · promedio{" "}
            {data.comanda_promedio_texto}
          </p>
        )}
      </section>

      {admin && (
      <section className="card" style={{ marginBottom: "1.5rem" }}>
        <div className="table-toolbar">
          <h2 style={{ margin: 0 }}>Configuración de precios</h2>
          {!editing && (
            <button type="button" className="btn btn--primary" onClick={() => setEditing(true)}>
              Editar
            </button>
          )}
        </div>

        {!editing ? (
          <div className="form-grid">
            <div className="panel-muted">
              <div className="stat-card__label">Margen de ganancia</div>
              <div className="stat-card__value">{config.margen_ganancia.toFixed(2)}%</div>
            </div>
            <div className="panel-muted">
              <div className="stat-card__label">Gastos fijos mensuales</div>
              <div className="stat-card__value">${config.gastos_fijos.toFixed(2)}</div>
              <p className="hint" style={{ marginTop: "0.5rem", marginBottom: 0 }}>
                Se distribuyen entre 1000 productos/mes
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="form-grid">
              <div className="form-row">
                <label>Margen de ganancia (%)</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={margenEditado}
                  onChange={(e) => setMargenEditado(e.target.value)}
                />
              </div>
              <div className="form-row">
                <label>Gastos fijos mensuales ($)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={gastosEditados}
                  onChange={(e) => setGastosEditados(e.target.value)}
                />
              </div>
            </div>
            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button type="button" className="btn btn--success" onClick={handleGuardarConfiguracion}>
                Guardar
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  setEditing(false);
                  setMargenEditado(config.margen_ganancia);
                  setGastosEditados(config.gastos_fijos);
                }}
              >
                Cancelar
              </button>
            </div>
          </>
        )}
      </section>
      )}

      <section className="card">
        <h2>Top productos</h2>
        {data.top_productos.length === 0 ? (
          <p className="empty-state">No hay ventas registradas aún.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Cantidad</th>
                  <th>Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {data.top_productos.map((p) => (
                  <tr key={p.id_producto}>
                    <td>{p.nombre}</td>
                    <td>{p.cantidad}</td>
                    <td>${p.subtotal.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
