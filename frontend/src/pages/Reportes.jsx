import { useState } from "react";
import {
  getVentasDia,
  getVentasMes,
  getVentasAnio,
  getVentasRango,
  getVentasComparar,
  getConsumoInsumos,
  getTiemposPreparacion,
  getProductosRanking,
  getPromocionesVentasReporte,
} from "../services/reportesService";
import PageHeader from "../components/PageHeader";
import { fechaMexicoISO } from "../utils/datetimeMx";

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

function fmt(n) {
  return `$${Number(n || 0).toFixed(2)}`;
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${Number(n).toFixed(1)}%`;
}

function fmtFecha(iso) {
  if (!iso) return "—";
  const [y, m, d] = String(iso).split("-");
  return `${d}/${m}/${y}`;
}

function ResumenOperaciones({ data, titulo = "Resumen del día" }) {
  if (!data) return null;
  const ventaTotal = data.total_dia ?? data.total_mes ?? data.total_anio ?? data.venta_total ?? 0;
  const tickets = data.numero_tickets ?? data.numero_ventas ?? 0;

  return (
    <div className="card" style={{ marginBottom: "1.5rem" }}>
      <h3 style={{ marginTop: 0 }}>{titulo}</h3>
      <div className="stats-grid">
        <div className="stat-card">
          <p className="stat-card__label">Venta total</p>
          <p className="stat-card__value">{fmt(ventaTotal)}</p>
        </div>
        <div className="stat-card">
          <p className="stat-card__label">Número de tickets</p>
          <p className="stat-card__value">{tickets}</p>
        </div>
        <div className="stat-card">
          <p className="stat-card__label">Ticket promedio</p>
          <p className="stat-card__value">{fmt(data.ticket_promedio)}</p>
        </div>
        <div className="stat-card">
          <p className="stat-card__label">Unidades vendidas</p>
          <p className="stat-card__value">{Number(data.unidades_vendidas || 0).toFixed(0)}</p>
        </div>
        <div className="stat-card">
          <p className="stat-card__label">Productos por ticket</p>
          <p className="stat-card__value">{Number(data.productos_por_ticket || 0).toFixed(2)}</p>
        </div>
        <div className="stat-card">
          <p className="stat-card__label">Promociones utilizadas</p>
          <p className="stat-card__value">{data.promociones_utilizadas ?? 0}</p>
        </div>
        <div className="stat-card">
          <p className="stat-card__label">Venta por promociones</p>
          <p className="stat-card__value">{fmt(data.venta_por_promociones)}</p>
        </div>
        {data.promedio_venta_diaria != null && (
          <div className="stat-card">
            <p className="stat-card__label">Promedio venta diaria</p>
            <p className="stat-card__value">{fmt(data.promedio_venta_diaria)}</p>
          </div>
        )}
        {data.promedio_tickets_diarios != null && (
          <div className="stat-card">
            <p className="stat-card__label">Promedio tickets/día</p>
            <p className="stat-card__value">{Number(data.promedio_tickets_diarios || 0).toFixed(1)}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function TablaProductos({ productos }) {
  if (!productos?.length) {
    return <p className="muted">Sin ventas de productos en este periodo.</p>;
  }

  return (
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
            <td>{fmt(p.subtotal)}</td>
            <td>{fmt(p.margen_total)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TablaDesgloseDias({ filas }) {
  if (!filas?.length) {
    return <p className="muted">Sin ventas en el periodo.</p>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Fecha</th>
          <th>Venta</th>
          <th>Tickets</th>
          <th>Ticket prom.</th>
          <th>Unidades</th>
          <th>Promociones</th>
        </tr>
      </thead>
      <tbody>
        {filas.map((d) => (
          <tr key={d.fecha}>
            <td>{fmtFecha(d.fecha)}</td>
            <td>{fmt(d.venta_total ?? d.total)}</td>
            <td>{d.numero_tickets ?? d.numero_ventas}</td>
            <td>{fmt(d.ticket_promedio)}</td>
            <td>{Number(d.unidades_vendidas || 0).toFixed(0)}</td>
            <td>{d.promociones_utilizadas ?? 0}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TablaRanking({ productos }) {
  if (!productos?.length) {
    return <p className="muted">Sin ventas de productos en este periodo.</p>;
  }

  return (
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
            <td>{fmt(p.subtotal)}</td>
            <td>{p.porcentaje}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TablaPromocionesDetalle({ promociones }) {
  if (!promociones?.length) return null;
  return (
    <div className="card" style={{ marginTop: "1.5rem" }}>
      <h3>Detalle de promociones</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Promoción</th>
            <th>Cantidad</th>
            <th>Importe</th>
            <th>Descuento</th>
          </tr>
        </thead>
        <tbody>
          {promociones.map((p) => (
            <tr key={p.id_promocion}>
              <td>{p.nombre}</td>
              <td>{p.cantidad}</td>
              <td>{fmt(p.importe)}</td>
              <td>{fmt(p.descuento_total)}</td>
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

  const [fecha, setFecha] = useState(fechaMexicoISO);
  const [fechaInicio, setFechaInicio] = useState(fechaMexicoISO);
  const [fechaFin, setFechaFin] = useState(fechaMexicoISO);
  const [fechaInicioA, setFechaInicioA] = useState("");
  const [fechaFinA, setFechaFinA] = useState("");
  const [fechaInicioB, setFechaInicioB] = useState(fechaMexicoISO);
  const [fechaFinB, setFechaFinB] = useState(fechaMexicoISO);

  const [anioMes, setAnioMes] = useState(hoy.getFullYear());
  const [mes, setMes] = useState(hoy.getMonth() + 1);
  const [anio, setAnio] = useState(hoy.getFullYear());

  const [reporte, setReporte] = useState(null);
  const [consumo, setConsumo] = useState(null);
  const [tiempos, setTiempos] = useState(null);
  const [ranking, setRanking] = useState(null);
  const [promociones, setPromociones] = useState(null);
  const [comparacion, setComparacion] = useState(null);
  const [promocionesPeriodo, setPromocionesPeriodo] = useState("dia");
  const [rankingPeriodo, setRankingPeriodo] = useState("dia");
  const [ordenRank, setOrdenRank] = useState("cantidad");
  const [loading, setLoading] = useState(false);

  const limpiarResultados = () => {
    setReporte(null);
    setConsumo(null);
    setTiempos(null);
    setRanking(null);
    setPromociones(null);
    setComparacion(null);
  };

  const presetSemanaAnterior = () => {
    const fin = new Date();
    fin.setDate(fin.getDate() - 7);
    const inicio = new Date(fin);
    inicio.setDate(inicio.getDate() - 6);
    const fmtIso = (d) => d.toISOString().slice(0, 10);
    setFechaInicioA(fmtIso(inicio));
    setFechaFinA(fmtIso(fin));
    setFechaInicioB(fechaMexicoISO);
    const hoyDate = new Date();
    const inicioSemana = new Date(hoyDate);
    inicioSemana.setDate(hoyDate.getDate() - 6);
    setFechaFinB(fechaMexicoISO);
    setFechaInicioB(inicioSemana.toISOString().slice(0, 10));
  };

  const cargar = async () => {
    setLoading(true);
    try {
      if (tab === "comparar") {
        if (!fechaInicioA || !fechaFinA || !fechaInicioB || !fechaFinB) {
          alert("Completa las fechas de ambos periodos");
          return;
        }
        const c = await getVentasComparar({
          fechaInicioA,
          fechaFinA,
          fechaInicioB,
          fechaFinB,
        });
        setReporte(null);
        setConsumo(null);
        setTiempos(null);
        setRanking(null);
        setPromociones(null);
        setComparacion(c);
        return;
      }

      if (tab === "rango") {
        if (!fechaInicio || !fechaFin) return alert("Selecciona fecha inicial y final");
        if (fechaFin < fechaInicio) return alert("La fecha final debe ser posterior o igual");
        const v = await getVentasRango(fechaInicio, fechaFin);
        setReporte(v);
        setConsumo(null);
        setTiempos(null);
        setRanking(null);
        setPromociones(null);
        setComparacion(null);
        return;
      }

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
        setPromociones(null);
        setComparacion(null);
      } else if (tab === "promociones") {
        const params = { periodo: promocionesPeriodo };
        if (promocionesPeriodo === "dia") {
          if (!fecha) return alert("Selecciona una fecha");
          params.fecha = fecha;
        } else if (promocionesPeriodo === "mes") {
          params.anio = anioMes;
          params.mes = mes;
        } else {
          params.anio = anio;
        }
        const p = await getPromocionesVentasReporte(params);
        setPromociones(p);
        setReporte(null);
        setConsumo(null);
        setTiempos(null);
        setRanking(null);
        setComparacion(null);
      } else if (tab === "tiempos") {
        if (!fecha) return alert("Selecciona una fecha");
        const t = await getTiemposPreparacion(fecha);
        setTiempos(t);
        setReporte(null);
        setConsumo(null);
        setRanking(null);
        setPromociones(null);
        setComparacion(null);
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
        setPromociones(null);
        setComparacion(null);
      } else if (tab === "mes") {
        const v = await getVentasMes(anioMes, mes);
        setReporte(v);
        setConsumo(null);
        setTiempos(null);
        setRanking(null);
        setPromociones(null);
        setComparacion(null);
      } else {
        const v = await getVentasAnio(anio);
        setReporte(v);
        setConsumo(null);
        setTiempos(null);
        setRanking(null);
        setPromociones(null);
        setComparacion(null);
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Error al cargar reporte");
    } finally {
      setLoading(false);
    }
  };

  const tituloResumen =
    tab === "dia"
      ? `Resumen del día — ${fmtFecha(reporte?.fecha)}`
      : tab === "mes"
        ? `Resumen del mes — ${reporte?.nombre_mes} ${reporte?.anio}`
        : tab === "anio"
          ? `Resumen del año — ${reporte?.anio}`
          : tab === "rango"
            ? `Resumen del periodo — ${fmtFecha(reporte?.fecha_inicio)} al ${fmtFecha(reporte?.fecha_fin)}`
            : "Resumen";

  return (
    <div>
      <PageHeader
        title="Reportes"
        subtitle="Análisis de ventas, tickets, promociones e insumos"
      />

      <div className="tabs" style={{ marginBottom: "1rem", flexWrap: "wrap" }}>
        {[
          { id: "dia", label: "Ventas por día" },
          { id: "rango", label: "Por rango" },
          { id: "comparar", label: "Comparar periodos" },
          { id: "mes", label: "Ventas por mes" },
          { id: "anio", label: "Ventas por año" },
          { id: "tiempos", label: "Tiempos por mesa" },
          { id: "ranking", label: "Top productos" },
          { id: "promociones", label: "Ventas por promoción" },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "btn btn--accent btn--sm" : "btn btn--ghost btn--sm"}
            onClick={() => {
              setTab(t.id);
              limpiarResultados();
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        {(tab === "ranking" || tab === "promociones") && (
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
                  (tab === "ranking" ? rankingPeriodo : promocionesPeriodo) === p.id
                    ? "btn btn--primary btn--sm"
                    : "btn btn--ghost btn--sm"
                }
                onClick={() => {
                  if (tab === "ranking") {
                    setRankingPeriodo(p.id);
                    setRanking(null);
                  } else {
                    setPromocionesPeriodo(p.id);
                    setPromociones(null);
                  }
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}

        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "flex-end" }}>
          {tab === "rango" && (
            <>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Fecha inicial</label>
                <input type="date" className="input" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
              </div>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Fecha final</label>
                <input type="date" className="input" value={fechaFin} onChange={(e) => setFechaFin(e.target.value)} />
              </div>
            </>
          )}

          {tab === "comparar" && (
            <>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Periodo A — inicio</label>
                <input type="date" className="input" value={fechaInicioA} onChange={(e) => setFechaInicioA(e.target.value)} />
              </div>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Periodo A — fin</label>
                <input type="date" className="input" value={fechaFinA} onChange={(e) => setFechaFinA(e.target.value)} />
              </div>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Periodo B — inicio</label>
                <input type="date" className="input" value={fechaInicioB} onChange={(e) => setFechaInicioB(e.target.value)} />
              </div>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Periodo B — fin</label>
                <input type="date" className="input" value={fechaFinB} onChange={(e) => setFechaFinB(e.target.value)} />
              </div>
              <button type="button" className="btn btn--ghost btn--sm" onClick={presetSemanaAnterior}>
                Semana ant. vs actual
              </button>
            </>
          )}

          {(tab === "dia" ||
            tab === "tiempos" ||
            (tab === "ranking" && rankingPeriodo === "dia") ||
            (tab === "promociones" && promocionesPeriodo === "dia")) && (
            <div className="form-row" style={{ margin: 0 }}>
              <label>Fecha</label>
              <input type="date" className="input" value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </div>
          )}

          {(tab === "mes" ||
            (tab === "ranking" && rankingPeriodo === "mes") ||
            (tab === "promociones" && promocionesPeriodo === "mes")) && (
            <>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Año</label>
                <input type="number" className="input" min={2020} max={2100} value={anioMes} onChange={(e) => setAnioMes(Number(e.target.value))} />
              </div>
              <div className="form-row" style={{ margin: 0 }}>
                <label>Mes</label>
                <select className="input" value={mes} onChange={(e) => setMes(Number(e.target.value))}>
                  {MESES.map((m) => (
                    <option key={m.v} value={m.v}>{m.l}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          {(tab === "anio" ||
            (tab === "ranking" && rankingPeriodo === "anio") ||
            (tab === "promociones" && promocionesPeriodo === "anio")) && (
            <div className="form-row" style={{ margin: 0 }}>
              <label>Año</label>
              <input type="number" className="input" min={2020} max={2100} value={anio} onChange={(e) => setAnio(Number(e.target.value))} />
            </div>
          )}

          {tab === "ranking" && (
            <div className="form-row" style={{ margin: 0 }}>
              <label>Ordenar por</label>
              <select className="input" value={ordenRank} onChange={(e) => { setOrdenRank(e.target.value); setRanking(null); }}>
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
          <ResumenOperaciones data={reporte} titulo={tituloResumen} />
          <TablaPromocionesDetalle promociones={reporte.promociones_detalle} />

          {(tab === "rango" || tab === "mes") && reporte.desglose_dias?.length > 0 && (
            <div className="card" style={{ marginBottom: "1.5rem" }}>
              <h3>Desglose por día</h3>
              <TablaDesgloseDias filas={reporte.desglose_dias} />
            </div>
          )}

          {tab === "anio" && reporte.desglose_meses?.length > 0 && (
            <div className="card" style={{ marginBottom: "1.5rem" }}>
              <h3>Desglose por mes</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>Mes</th>
                    <th>Venta</th>
                    <th>Tickets</th>
                    <th>Ticket prom.</th>
                    <th>Unidades</th>
                    <th>Promociones</th>
                  </tr>
                </thead>
                <tbody>
                  {reporte.desglose_meses.map((m) => (
                    <tr key={m.mes}>
                      <td>{m.nombre_mes}</td>
                      <td>{fmt(m.venta_total ?? m.total)}</td>
                      <td>{m.numero_tickets ?? m.numero_ventas}</td>
                      <td>{fmt(m.ticket_promedio)}</td>
                      <td>{Number(m.unidades_vendidas || 0).toFixed(0)}</td>
                      <td>{m.promociones_utilizadas ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="card">
            <h3>Productos vendidos</h3>
            <TablaProductos productos={reporte.productos} />
          </div>
        </>
      )}

      {comparacion && (
        <>
          <div className="card" style={{ marginBottom: "1.5rem" }}>
            <h3>Comparación de periodos</h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Métrica</th>
                  <th>
                    Periodo A<br />
                    <span className="hint">{fmtFecha(comparacion.periodo_a.fecha_inicio)} — {fmtFecha(comparacion.periodo_a.fecha_fin)}</span>
                  </th>
                  <th>
                    Periodo B<br />
                    <span className="hint">{fmtFecha(comparacion.periodo_b.fecha_inicio)} — {fmtFecha(comparacion.periodo_b.fecha_fin)}</span>
                  </th>
                  <th>Variación</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["Venta total", "venta_total", fmt],
                  ["Tickets", "numero_tickets", (n) => n],
                  ["Ticket promedio", "ticket_promedio", fmt],
                  ["Unidades vendidas", "unidades_vendidas", (n) => Number(n).toFixed(0)],
                  ["Productos por ticket", "productos_por_ticket", (n) => Number(n).toFixed(2)],
                ].map(([label, key, formatter]) => (
                  <tr key={key}>
                    <td>{label}</td>
                    <td>{formatter(comparacion.periodo_a[key])}</td>
                    <td>{formatter(comparacion.periodo_b[key])}</td>
                    <td>{fmtPct(comparacion.variacion[`${key}_pct`])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {consumo && (
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <h3>Consumo de insumos (día seleccionado)</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Insumo</th>
                <th>Cantidad consumida</th>
                <th>Stock actual</th>
                <th>Stock mínimo</th>
                <th>Alerta</th>
              </tr>
            </thead>
            <tbody>
              {consumo.consumo.map((i) => (
                <tr key={i.id_insumo}>
                  <td>{i.nombre}</td>
                  <td>{i.cantidad_consumida}</td>
                  <td>{i.stock_actual}</td>
                  <td>{i.stock_minimo}</td>
                  <td>{i.alerta ? "⚠ Bajo stock" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
                    — {mesa.total_pedidos} pedido(s) · prom. {mesa.promedio_texto} · máx {mesa.max_texto}
                  </span>
                </h3>
                {mesa.pedidos.map((ped) => (
                  <div key={ped.id_pedido} className="panel-muted" style={{ marginTop: "1rem" }}>
                    <p>
                      <strong>Pedido #{ped.id_pedido}</strong> · {ped.duracion_pedido_texto}
                    </p>
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
                ))}
              </div>
            ))
          )}
        </>
      )}

      {promociones && (
        <>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card">
              <p className="stat-card__label">Periodo</p>
              <p className="stat-card__value">{promociones.periodo_label}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Unidades con promo</p>
              <p className="stat-card__value">{promociones.total_ventas_con_promo}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Descuento total</p>
              <p className="stat-card__value">{fmt(promociones.total_descuento)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Ingresos con promo</p>
              <p className="stat-card__value">{fmt(promociones.total_ingresos_con_promo)}</p>
            </div>
          </div>
          <div className="card">
            <h3>Ventas por promoción</h3>
            {!promociones.promociones_usadas?.length ? (
              <p className="empty-state">Sin ventas con promoción en este periodo.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Promoción</th>
                    <th>Usos (unidades)</th>
                    <th>Descuento total</th>
                    <th>Ingresos</th>
                  </tr>
                </thead>
                <tbody>
                  {promociones.promociones_usadas.map((p) => (
                    <tr key={p.id_promocion}>
                      <td>{p.nombre}</td>
                      <td>{p.usos}</td>
                      <td>{fmt(p.descuento_total)}</td>
                      <td>{fmt(p.ingresos_con_promo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
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
              <p className="stat-card__value">{fmt(ranking.total_ingresos)}</p>
            </div>
          </div>
          <div className="card">
            <h3>Ranking — {ordenRank === "cantidad" ? "por cantidad" : "por ingresos"}</h3>
            <TablaRanking productos={ranking.productos} />
          </div>
        </>
      )}

      <p className="hint" style={{ marginTop: "1.5rem" }}>
        Tickets: cada fila en <code>ventas</code> (id_venta) es una operación cerrada — válido en todo el histórico.
        Promociones: métricas confiables solo en ventas con <code>id_promocion</code> registrado en detalle.
      </p>
    </div>
  );
}
