import { useState } from "react";
import {
  getVentasDia,
  getVentasMes,
  getVentasAnio,
  getConsumoInsumos,
  getTiemposPreparacion,
  getProductosRanking,
} from "../services/reportesService";
import PageHeader from "../components/PageHeader";

const MESES = [
  { v: 1, l: "Enero" },
  { v: 2, l: "Febrero" },
  { v: 3, l: "Marzo" },
  { v: 4, l: "Abril" },
  { v: 5, l: "Mayo" },
  { v: 6, l: "Junio" },
  { v: 7, l: "Julio" },
  { v: 8, l: "Agosto" },
  { v: 9, l: "Septiembre" },
  { v: 10, l: "Octubre" },
  { v: 11, l: "Noviembre" },
  { v: 12, l: "Diciembre" },
];

function TablaRanking({ productos, orden }) {
  if (!productos?.length) {
    return <p className="muted">Sin ventas de productos en este periodo.</p>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
      <thead>
        <tr>
          <th>#</th>
          <th>Producto</th>
          <th>Categoría</th>
          <th>Cantidad</th>
          <th>Ingresos</th>
          <th>% del total</th>
        </tr>
      </thead>
      <tbody>
        {productos.map((p) => (
          <tr key={p.id_producto}>
            <td>
              <span className={`ranking-pos ranking-pos--${p.posicion <= 3 ? p.posicion : "n"}`}>
                {p.posicion}
              </span>
            </td>
            <td>{p.nombre}</td>
            <td>{p.categoria || "—"}</td>
            <td>{p.cantidad}</td>
            <td>${p.subtotal.toFixed(2)}</td>
            <td>{p.porcentaje}%</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function TablaProductos({ productos }) {
  if (!productos?.length) {
    return <p className="muted">Sin ventas de productos en este periodo.</p>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
      <thead>
        <tr>
          <th>Producto</th>
          <th>Cantidad</th>
          <th>Subtotal</th>
          <th>Margen total</th>
        </tr>
      </thead>
      <tbody>
        {productos.map((p) => (
          <tr key={p.id_producto}>
            <td>{p.nombre}</td>
            <td>{p.cantidad}</td>
            <td>${p.subtotal.toFixed(2)}</td>
            <td>${p.margen_total.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

export default function Reportes() {
  const hoy = new Date();
  const [tab, setTab] = useState("dia");

  const [fecha, setFecha] = useState(hoy.toISOString().slice(0, 10));
  const [anioMes, setAnioMes] = useState(hoy.getFullYear());
  const [mes, setMes] = useState(hoy.getMonth() + 1);
  const [anio, setAnio] = useState(hoy.getFullYear());

  const [reporte, setReporte] = useState(null);
  const [consumo, setConsumo] = useState(null);
  const [tiempos, setTiempos] = useState(null);
  const [ranking, setRanking] = useState(null);
  const [rankingPeriodo, setRankingPeriodo] = useState("dia");
  const [ordenRank, setOrdenRank] = useState("cantidad");
  const [loading, setLoading] = useState(false);

  const cargar = async () => {
    setLoading(true);
    try {
      if (tab === "ranking") {
        const params = { periodo: rankingPeriodo, orden: ordenRank };
        if (rankingPeriodo === "dia") {
          if (!fecha) return alert("Selecciona una fecha");
          params.fecha = fecha;
        } else if (rankingPeriodo === "mes") {
          params.anio = anioMes;
          params.mes = mes;
        } else {
          params.anio = anio;
        }
        const r = await getProductosRanking(params);
        setRanking(r);
        setReporte(null);
        setConsumo(null);
        setTiempos(null);
      } else if (tab === "tiempos") {
        if (!fecha) return alert("Selecciona una fecha");
        const t = await getTiemposPreparacion(fecha);
        setTiempos(t);
        setReporte(null);
        setConsumo(null);
        setRanking(null);
      } else if (tab === "dia") {
        if (!fecha) return alert("Selecciona una fecha");
        const [v, c] = await Promise.all([
          getVentasDia(fecha),
          getConsumoInsumos(fecha),
        ]);
        setReporte(v);
        setConsumo(c);
        setTiempos(null);
        setRanking(null);
      } else if (tab === "mes") {
        const v = await getVentasMes(anioMes, mes);
        setReporte(v);
        setConsumo(null);
        setTiempos(null);
        setRanking(null);
      } else {
        const v = await getVentasAnio(anio);
        setReporte(v);
        setConsumo(null);
        setTiempos(null);
        setRanking(null);
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Error al cargar reporte");
    } finally {
      setLoading(false);
    }
  };

  const totalLabel =
    tab === "dia"
      ? reporte?.total_dia
      : tab === "mes"
        ? reporte?.total_mes
        : reporte?.total_anio;

  return (
    <div>
      <PageHeader
        title="Reportes"
        subtitle="Ventas, insumos y tiempos de preparación en cocina"
      />

      <div className="tabs" style={{ marginBottom: "1rem" }}>
        {[
          { id: "dia", label: "Ventas por día" },
          { id: "mes", label: "Ventas por mes" },
          { id: "anio", label: "Ventas por año" },
          { id: "tiempos", label: "Tiempos por mesa" },
          { id: "ranking", label: "Top productos" },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "btn btn--accent btn--sm" : "btn btn--ghost btn--sm"}
            onClick={() => {
              setTab(t.id);
              setReporte(null);
              setConsumo(null);
              setTiempos(null);
              setRanking(null);
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        {tab === "ranking" && (
          <div className="tabs" style={{ marginBottom: "1rem" }}>
            {[
              { id: "dia", label: "Por día" },
              { id: "mes", label: "Por mes" },
              { id: "anio", label: "Por año" },
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                className={
                  rankingPeriodo === p.id ? "btn btn--primary btn--sm" : "btn btn--ghost btn--sm"
                }
                onClick={() => {
                  setRankingPeriodo(p.id);
                  setRanking(null);
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}

        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "flex-end" }}>
          {(tab === "dia" || tab === "tiempos" || (tab === "ranking" && rankingPeriodo === "dia")) && (
            <div className="form-row" style={{ margin: 0 }}>
              <label>Fecha</label>
              <input
                type="date"
                className="input"
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
              />
            </div>
          )}

          {(tab === "mes" || (tab === "ranking" && rankingPeriodo === "mes")) && (
            <>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Año</label>
                <input
                  type="number"
                  className="input"
                  min={2020}
                  max={2100}
                  value={anioMes}
                  onChange={(e) => setAnioMes(Number(e.target.value))}
                />
              </div>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Mes</label>
                <select
                  className="input"
                  value={mes}
                  onChange={(e) => setMes(Number(e.target.value))}
                >
                  {MESES.map((m) => (
                    <option key={m.v} value={m.v}>
                      {m.l}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}

          {(tab === "anio" || (tab === "ranking" && rankingPeriodo === "anio")) && (
            <div className="form-row" style={{ margin: 0 }}>
              <label>Año</label>
              <input
                type="number"
                className="input"
                min={2020}
                max={2100}
                value={anio}
                onChange={(e) => setAnio(Number(e.target.value))}
              />
            </div>
          )}

          {tab === "ranking" && (
            <div className="form-row" style={{ margin: 0 }}>
              <label>Ordenar por</label>
              <select
                className="input"
                value={ordenRank}
                onChange={(e) => {
                  setOrdenRank(e.target.value);
                  setRanking(null);
                }}
              >
                <option value="cantidad">Cantidad vendida</option>
                <option value="subtotal">Ingresos ($)</option>
              </select>
            </div>
          )}

          <button type="button" className="btn btn--accent" onClick={cargar} disabled={loading}>
            {loading ? "Cargando…" : "Generar reporte"}
          </button>
        </div>
      </div>

      {reporte && (
        <>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card">
              <p className="stat-card__label">Total</p>
              <p className="stat-card__value">${Number(totalLabel || 0).toFixed(2)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Número de ventas</p>
              <p className="stat-card__value">{reporte.numero_ventas}</p>
            </div>
            {tab === "mes" && (
              <div className="stat-card">
                <p className="stat-card__label">Periodo</p>
                <p className="stat-card__value">{reporte.nombre_mes} {reporte.anio}</p>
              </div>
            )}
            {tab === "anio" && (
              <div className="stat-card">
                <p className="stat-card__label">Año</p>
                <p className="stat-card__value">{reporte.anio}</p>
              </div>
            )}
          </div>

          {tab === "mes" && reporte.desglose_dias?.length > 0 && (
            <div className="card" style={{ marginBottom: "1.5rem" }}>
              <h3>Desglose por día</h3>
              <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Total</th>
                    <th>Ventas</th>
                  </tr>
                </thead>
                <tbody>
                  {reporte.desglose_dias.map((d) => (
                    <tr key={d.fecha}>
                      <td>{d.fecha}</td>
                      <td>${d.total.toFixed(2)}</td>
                      <td>{d.numero_ventas}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          )}

          {tab === "anio" && reporte.desglose_meses?.length > 0 && (
            <div className="card" style={{ marginBottom: "1.5rem" }}>
              <h3>Desglose por mes</h3>
              <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Mes</th>
                    <th>Total</th>
                    <th>Ventas</th>
                  </tr>
                </thead>
                <tbody>
                  {reporte.desglose_meses.map((m) => (
                    <tr key={m.mes}>
                      <td>{m.nombre_mes}</td>
                      <td>${m.total.toFixed(2)}</td>
                      <td>{m.numero_ventas}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          )}

          <div className="card">
            <h3>Productos vendidos (mayor a menor)</h3>
            <TablaProductos productos={reporte.productos} />
          </div>
        </>
      )}

      {consumo && (
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <h3>Consumo de insumos (día seleccionado)</h3>
          <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Insumo</th>
                <th>Consumido</th>
                <th>Bodega</th>
                <th>Cafetería</th>
                <th>Mín. caf.</th>
                <th>Alerta</th>
              </tr>
            </thead>
            <tbody>
              {consumo.consumo.map((i) => (
                <tr key={i.id_insumo}>
                  <td>{i.nombre}</td>
                  <td>{i.cantidad_consumida}</td>
                  <td>{i.stock_bodega}</td>
                  <td>{i.stock_cafeteria}</td>
                  <td>{i.stock_minimo}</td>
                  <td>{i.alerta ? "⚠ Cafetería baja" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {tiempos && (
        <>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card">
              <p className="stat-card__label">Pedidos completados</p>
              <p className="stat-card__value">{tiempos.total_pedidos ?? 0}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Promedio general</p>
              <p className="stat-card__value">{tiempos.promedio_general_texto}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Mesas con actividad</p>
              <p className="stat-card__value">{tiempos.por_mesa?.length ?? 0}</p>
            </div>
          </div>

          {tiempos.por_mesa?.length === 0 ? (
            <p className="empty-state">No hay pedidos completados en cocina para esta fecha.</p>
          ) : (
            tiempos.por_mesa.map((mesa) => (
              <div key={mesa.numero_mesa} className="card" style={{ marginBottom: "1.5rem" }}>
                <h3>
                  Mesa {mesa.numero_mesa}{" "}
                  <span className="hint">
                    — {mesa.total_pedidos} pedido(s) · prom. {mesa.promedio_texto} · máx{" "}
                    {mesa.max_texto}
                  </span>
                </h3>
                {mesa.pedidos.map((ped) => (
                  <div key={ped.id_pedido} className="panel-muted" style={{ marginTop: "1rem" }}>
                    <p>
                      <strong>Pedido #{ped.id_pedido}</strong> · {ped.duracion_pedido_texto}{" "}
                      <span className="hint">
                        ({new Date(ped.inicio).toLocaleTimeString()} →{" "}
                        {new Date(ped.fin).toLocaleTimeString()})
                      </span>
                    </p>
                    <div className="table-wrap">
                    <table className="table" style={{ marginTop: "0.5rem" }}>
                      <thead>
                        <tr>
                          <th>Producto</th>
                          <th>Cant.</th>
                          <th>Tiempo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ped.lineas.map((l, i) => (
                          <tr key={`${ped.id_pedido}-${i}`}>
                            <td>{l.nombre_producto}</td>
                            <td>{l.cantidad}</td>
                            <td>{l.duracion_texto}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </div>
                  </div>
                ))}
              </div>
            ))
          )}
        </>
      )}

      {ranking && (
        <>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card">
              <p className="stat-card__label">Periodo</p>
              <p className="stat-card__value">{ranking.periodo_label}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Productos distintos</p>
              <p className="stat-card__value">{ranking.productos?.length ?? 0}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Unidades vendidas</p>
              <p className="stat-card__value">{ranking.total_unidades}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Ingresos totales</p>
              <p className="stat-card__value">${ranking.total_ingresos?.toFixed(2)}</p>
            </div>
          </div>

          <div className="card">
            <h3>
              Ranking —{" "}
              {ordenRank === "cantidad" ? "por cantidad vendida" : "por ingresos"}
            </h3>
            <TablaRanking productos={ranking.productos} orden={ordenRank} />
          </div>
        </>
      )}
    </div>
  );
}
