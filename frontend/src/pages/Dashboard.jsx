import { useEffect, useState } from "react";
import { getResumenDashboard } from "../services/dashboardService";
import { getConfiguracion, updateConfiguracion } from "../services/configuracionService";
import PageHeader from "../components/PageHeader";
import { useAuthStore } from "../store/authStore";
import { isAdmin } from "../config/permissions";

export default function Dashboard() {
  const rol = useAuthStore((state) => state.user?.rol);
  const admin = isAdmin(rol);
  const [data, setData] = useState(null);
  const [config, setConfig] = useState(null);
  const [editing, setEditing] = useState(false);
  const [margenEditado, setMargenEditado] = useState("");
  const [gastosEditados, setGastosEditados] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const resumenData = await getResumenDashboard();
        setData(resumenData);

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
    load();
  }, [admin]);

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
        subtitle="Resumen del día y configuración de precios"
      />

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-card__label">Ventas hoy</div>
          <div className="stat-card__value">${data.total_hoy.toFixed(2)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Ventas del día</div>
          <div className="stat-card__value">{data.num_ventas_hoy}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Acumulado</div>
          <div className="stat-card__value">${data.total_general.toFixed(2)}</div>
        </div>
      </div>

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
