import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { HiOutlineArrowPath } from "react-icons/hi2";
import { getComandaPendientes, marcarLineaListo, marcarCancelacionVista } from "../services/pedidosService";
import { formatApiError } from "../utils/apiError";
import PageHeader from "../components/PageHeader";
import ElapsedTimer from "../components/ElapsedTimer";
import { formatDuration } from "../utils/formatDuration";
import { elapsedSecondsUtc, parseUtcDate } from "../utils/parseUtcDate";

export default function Comandera() {
  const [lineas, setLineas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [procesando, setProcesando] = useState(null);
  const procesandoRef = useRef(null);

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
    const t = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const conRefreshSiConflicto = async (run) => {
    try {
      await run();
      await load();
    } catch (err) {
      if (err.response?.status === 409) {
        alert(formatApiError(err, "La comandera cambió. Se actualiza la lista."));
        await load();
        return;
      }
      alert(formatApiError(err, "No se pudo completar la operación"));
    }
  };

  const marcar = async (linea) => {
    const key = `listo-${linea.id_detalle_pedido}`;
    if (procesandoRef.current) return;
    procesandoRef.current = key;
    setProcesando(key);
    try {
      await conRefreshSiConflicto(() =>
        marcarLineaListo(linea.id_detalle_pedido, 1, {
          cantidad_actual: linea.cantidad,
          cantidad_lista_actual: linea.cantidad_lista,
        })
      );
    } finally {
      procesandoRef.current = null;
      setProcesando(null);
    }
  };

  const marcarTodo = async (linea) => {
    const key = `todo-${linea.id_detalle_pedido}`;
    if (procesandoRef.current) return;
    procesandoRef.current = key;
    setProcesando(key);
    try {
      await conRefreshSiConflicto(() =>
        marcarLineaListo(linea.id_detalle_pedido, linea.cantidad_pendiente, {
          cantidad_actual: linea.cantidad,
          cantidad_lista_actual: linea.cantidad_lista,
        })
      );
    } finally {
      procesandoRef.current = null;
      setProcesando(null);
    }
  };

  const marcarAvisoVisto = async (idCancelacion) => {
    const key = `visto-${idCancelacion}`;
    if (procesandoRef.current) return;
    procesandoRef.current = key;
    setProcesando(key);
    try {
      await marcarCancelacionVista(idCancelacion);
      await load();
    } catch (err) {
      alert(formatApiError(err, "No se pudo marcar el aviso"));
    } finally {
      procesandoRef.current = null;
      setProcesando(null);
    }
  };

  const porPedido = useMemo(() => {
    const acc = {};
    for (const l of lineas) {
      const key = l.id_pedido;
      if (!acc[key]) {
        acc[key] = {
          id_pedido: l.id_pedido,
          para_llevar: l.para_llevar,
          numero_mesa: l.numero_mesa,
          estado_pedido: l.estado_pedido,
          cuenta_cobrada: l.cuenta_cobrada,
          lineas: [],
        };
      }
      acc[key].lineas.push(l);
      if (l.cuenta_cobrada) acc[key].cuenta_cobrada = true;
      if (l.estado_pedido) acc[key].estado_pedido = l.estado_pedido;
    }
    return Object.values(acc).sort((a, b) => {
      const ta = Math.min(...a.lineas.map((x) => parseUtcDate(x.fecha_envio_comanda)?.getTime() ?? Infinity));
      const tb = Math.min(...b.lineas.map((x) => parseUtcDate(x.fecha_envio_comanda)?.getTime() ?? Infinity));
      return ta - tb;
    });
  }, [lineas]);

  const maxSegundosPedido = (items) =>
    Math.max(...items.map((l) => l.segundos_en_preparacion ?? 0), 0);

  return (
    <div className="page comandera-page">
      <PageHeader
        title="Comandera"
        subtitle="Cronómetro desde que se confirma el pedido en ventas hasta marcar listo"
      >
        <button
          type="button"
          className="btn btn--secondary inline-flex items-center gap-2"
          onClick={load}
          disabled={loading}
        >
          <HiOutlineArrowPath className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden />
          {loading ? "Actualizando…" : "Actualizar"}
        </button>
      </PageHeader>

      {lineas.length === 0 && !loading && (
        <p className="empty-state">No hay pedidos pendientes en cocina/barra</p>
      )}

      <div className="comandera-grid">
        {porPedido.map((grupo) => {
          const items = grupo.lineas;
          const earliestSince = items.reduce((min, l) => {
            if (!l.fecha_envio_comanda) return min;
            if (!min) return l.fecha_envio_comanda;
            const a = parseUtcDate(l.fecha_envio_comanda);
            const b = parseUtcDate(min);
            if (!a) return min;
            if (!b) return l.fecha_envio_comanda;
            return a.getTime() < b.getTime() ? l.fecha_envio_comanda : min;
          }, null);
          const pedidoSegs = elapsedSecondsUtc(
            earliestSince,
            nowMs,
            maxSegundosPedido(items)
          );
          const paraLlevar = grupo.para_llevar || grupo.numero_mesa === 99;
          return (
            <section
              key={grupo.id_pedido}
              className={`comandera-mesa card ${paraLlevar ? "comandera-mesa--para-llevar" : ""}`}
            >
              <div className="comandera-mesa__header">
                <div>
                  {paraLlevar ? (
                    <>
                      <span className="badge badge--ok">PARA LLEVAR</span>
                      <h2 className="comandera-mesa__title">Pedido #{grupo.id_pedido}</h2>
                    </>
                  ) : (
                    <>
                      <h2 className="comandera-mesa__title">Mesa {grupo.numero_mesa}</h2>
                      <p className="hint">Pedido #{grupo.id_pedido}</p>
                    </>
                  )}
                  {grupo.cuenta_cobrada && (
                    <span className="badge badge--danger" style={{ marginLeft: "0.35rem" }}>
                      CUENTA COBRADA
                    </span>
                  )}
                </div>
                <ElapsedTimer since={earliestSince} className="comandera-timer--mesa" />
              </div>
              <ul className="comandera-list">
                {items.map((l) => {
                  const esAviso = l.tipo === "CANCELACION";
                  const keyVisto = `visto-${l.id_cancelacion}`;
                  const keyListo = `listo-${l.id_detalle_pedido}`;
                  const keyTodo = `todo-${l.id_detalle_pedido}`;
                  return (
                  <li
                    key={esAviso ? `cancel-${l.id_cancelacion}` : `linea-${l.id_detalle_pedido}`}
                    className={`comandera-item${esAviso ? " comandera-item--aviso" : ""}`}
                  >
                    <div className="comandera-item__main">
                      <div className="comandera-item__title-row">
                        <strong>
                          {l.nombre_producto}
                          {!esAviso && l.cantidad_pendiente > 1 && (
                            <span className="comandera-qty"> × {l.cantidad_pendiente}</span>
                          )}
                        </strong>
                        {!esAviso && (
                        <ElapsedTimer
                          since={l.fecha_envio_comanda}
                          initialSeconds={l.segundos_en_preparacion}
                        />
                        )}
                      </div>
                      {esAviso && (
                        <>
                          <span className="badge badge--danger comandera-aviso">
                            {l.aviso_texto || "CANCELADO"}
                          </span>
                          {paraLlevar && (
                            <span className="badge badge--ok">PARA LLEVAR</span>
                          )}
                          {l.cuenta_cobrada && (
                            <span className="badge badge--danger">CUENTA COBRADA</span>
                          )}
                        </>
                      )}
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
                      {l.comentario && (
                        <p className="cart-item__comentario">📝 {l.comentario}</p>
                      )}
                      {!esAviso && l.cantidad_pendiente < l.cantidad && (
                        <p className="hint">
                          {l.cantidad_lista}/{l.cantidad} listos
                        </p>
                      )}
                    </div>
                    <div className="comandera-item__actions">
                      {esAviso ? (
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm comandera-visto"
                          onClick={() => marcarAvisoVisto(l.id_cancelacion)}
                          disabled={Boolean(procesando)}
                        >
                          {procesando === keyVisto ? "Marcando…" : "Vi / Atendí"}
                        </button>
                      ) : (
                        <>
                      <button
                        type="button"
                        className="btn btn--success btn--sm"
                        onClick={() => marcar(l)}
                        disabled={Boolean(procesando)}
                      >
                        {procesando === keyListo ? "Marcando…" : "1 listo"}
                      </button>
                      {l.cantidad_pendiente > 1 && (
                        <button
                          type="button"
                          className="btn btn--primary btn--sm"
                          onClick={() => marcarTodo(l)}
                          disabled={Boolean(procesando)}
                        >
                          {procesando === keyTodo ? "Marcando…" : "Todo"}
                        </button>
                      )}
                        </>
                      )}
                    </div>
                  </li>
                  );
                })}
              </ul>
              <p className="hint comandera-mesa__footer">
                Tiempo en preparación: {formatDuration(pedidoSegs)}
              </p>
            </section>
          );
        })}
      </div>
    </div>
  );
}
