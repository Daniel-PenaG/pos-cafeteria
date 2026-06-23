import { useEffect, useState, useCallback } from "react";
import { getComandaPendientes, marcarLineaListo } from "../services/pedidosService";
import PageHeader from "../components/PageHeader";
import ElapsedTimer, { formatDuration } from "../components/ElapsedTimer";

export default function Comandera() {
  const [lineas, setLineas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [, setTick] = useState(0);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getComandaPendientes();
      setLineas(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const marcar = async (id) => {
    try {
      await marcarLineaListo(id, 1);
      load();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al marcar");
    }
  };

  const marcarTodo = async (id, cantidadPendiente) => {
    try {
      await marcarLineaListo(id, cantidadPendiente);
      load();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al marcar");
    }
  };

  const porMesa = lineas.reduce((acc, l) => {
    const m = l.numero_mesa;
    if (!acc[m]) acc[m] = [];
    acc[m].push(l);
    return acc;
  }, {});

  const mesasOrdenadas = Object.keys(porMesa).sort((a, b) => Number(a) - Number(b));

  const maxSegundosMesa = (items) =>
    Math.max(...items.map((l) => l.segundos_en_preparacion ?? 0), 0);

  return (
    <div className="page comandera-page">
      <PageHeader
        title="Comandera"
        subtitle="Cronómetro desde que se envía a cocina hasta marcar listo"
      >
        <button type="button" className="btn btn--secondary" onClick={load} disabled={loading}>
          {loading ? "Actualizando…" : "Actualizar"}
        </button>
      </PageHeader>

      {lineas.length === 0 && !loading && (
        <p className="empty-state">No hay pedidos pendientes en cocina/barra</p>
      )}

      <div className="comandera-grid">
        {mesasOrdenadas.map((mesa) => {
          const items = porMesa[mesa];
          const earliestSince = items.reduce((min, l) => {
            if (!l.fecha_envio_comanda) return min;
            if (!min) return l.fecha_envio_comanda;
            return new Date(l.fecha_envio_comanda) < new Date(min)
              ? l.fecha_envio_comanda
              : min;
          }, null);
          const mesaSegs = maxSegundosMesa(items);
          return (
            <section key={mesa} className="comandera-mesa card">
              <div className="comandera-mesa__header">
                <h2 className="comandera-mesa__title">Mesa {mesa}</h2>
                <ElapsedTimer since={earliestSince} className="comandera-timer--mesa" />
              </div>
              <ul className="comandera-list">
                {items.map((l) => (
                  <li key={l.id_detalle_pedido} className="comandera-item">
                    <div className="comandera-item__main">
                      <div className="comandera-item__title-row">
                        <strong>
                          {l.nombre_producto}
                          {l.cantidad_pendiente > 1 && (
                            <span className="comandera-qty"> × {l.cantidad_pendiente}</span>
                          )}
                        </strong>
                        <ElapsedTimer
                          since={l.fecha_envio_comanda}
                          initialSeconds={l.segundos_en_preparacion}
                        />
                      </div>
                      {l.nombre_promocion && (
                        <span className="badge">{l.nombre_promocion}</span>
                      )}
                      {l.extras?.length > 0 && (
                        <ul className="cart-item__extras">
                          {l.extras.map((e) => (
                            <li key={e.id_extra}>+ {e.nombre}</li>
                          ))}
                        </ul>
                      )}
                      {l.cantidad_pendiente < l.cantidad && (
                        <p className="hint">
                          {l.cantidad_lista}/{l.cantidad} listos
                        </p>
                      )}
                      {l.fecha_envio_comanda && (
                        <p className="hint">
                          Enviado: {new Date(l.fecha_envio_comanda).toLocaleTimeString()}
                        </p>
                      )}
                    </div>
                    <div className="comandera-item__actions">
                      <button
                        type="button"
                        className="btn btn--success btn--sm"
                        onClick={() => marcar(l.id_detalle_pedido)}
                      >
                        1 listo
                      </button>
                      {l.cantidad_pendiente > 1 && (
                        <button
                          type="button"
                          className="btn btn--primary btn--sm"
                          onClick={() =>
                            marcarTodo(l.id_detalle_pedido, l.cantidad_pendiente)
                          }
                        >
                          Todo
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              <p className="hint comandera-mesa__footer">
                Tiempo máximo en mesa: {formatDuration(mesaSegs)}
              </p>
            </section>
          );
        })}
      </div>
    </div>
  );
}
