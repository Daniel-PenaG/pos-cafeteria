import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { flushSync } from "react-dom";
import { HiOutlineArrowPath } from "react-icons/hi2";
import { getComandaPendientes, marcarLineaListo, marcarCancelacionVista } from "../services/pedidosService";
import { formatApiError } from "../utils/apiError";
import { toastError } from "../store/toastStore";
import PageHeader from "../components/PageHeader";
import ElapsedTimer from "../components/ElapsedTimer";
import { formatDuration } from "../utils/formatDuration";
import { elapsedSecondsUtc, parseUtcDate } from "../utils/parseUtcDate";
import {
  applyOptimisticListoPlan,
  buildOptimisticListoPlan,
  isStaleListoOp,
  reconcileListoServerLine,
  resolveComanderaMutacionError,
  resolveComanderaMutacionExito,
  rollbackOptimisticLinea,
  shouldSkipComanderaFetch,
} from "../utils/comanderaSync.js";

function markListoE2e(phase) {
  if (import.meta.env.MODE === "e2e") {
    window.__posE2e?.markListo?.(phase);
  }
}

export default function Comandera() {
  const [lineas, setLineas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [procesando, setProcesando] = useState(null);
  const procesandoRef = useRef(null);
  const [lineSyncIds, setLineSyncIds] = useState(() => new Set());
  const lineBusyRef = useRef(new Set());
  const lineOpSeqRef = useRef({});
  const mountedRef = useRef(true);
  const cargandoRef = useRef(false);
  const abortRef = useRef(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async (forzar = false) => {
    if (
      shouldSkipComanderaFetch({
        cargando: cargandoRef.current,
        visibilityState: typeof document !== "undefined" ? document.visibilityState : "visible",
        forzar,
      })
    ) {
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    cargandoRef.current = true;
    try {
      setLoading(true);
      const data = await getComandaPendientes({ signal: controller.signal });
      if (!controller.signal.aborted) setLineas(data);
    } catch (err) {
      if (err?.code === "ERR_CANCELED" || err?.name === "CanceledError") return;
      console.error(err);
    } finally {
      cargandoRef.current = false;
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(true);
    const onVis = () => {
      if (document.visibilityState === "visible") load(true);
    };
    document.addEventListener("visibilitychange", onVis);
    const t = setInterval(() => load(false), 8000);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", onVis);
      abortRef.current?.abort();
    };
  }, [load]);

  useEffect(() => {
    const t = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const setLineSyncing = useCallback((id, syncing) => {
    if (syncing) lineBusyRef.current.add(id);
    else lineBusyRef.current.delete(id);
    setLineSyncIds((prev) => {
      const next = new Set(prev);
      if (syncing) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const ejecutarMarcarListo = async (linea, cantidad) => {
    const id = linea.id_detalle_pedido;
    if (lineBusyRef.current.has(id)) return;

    markListoE2e("handler_start");
    const opId = (lineOpSeqRef.current[id] || 0) + 1;
    lineOpSeqRef.current[id] = opId;

    const plan = buildOptimisticListoPlan(linea, cantidad);
    markListoE2e("optimistic_requested");
    flushSync(() => {
      setLineas((prev) => applyOptimisticListoPlan(prev, plan));
      setLineSyncing(id, true);
    });
    markListoE2e("visual_local");
    const listoBtn = document.querySelector(`[data-nav-listo-btn="${id}"]`);
    if (listoBtn?.textContent?.includes("Sincronizando")) {
      markListoE2e("dom_syncing_visible");
    }
    requestAnimationFrame(() => {
      markListoE2e("raf_after_paint");
    });

    try {
      markListoE2e("request_start");
      const data = await marcarLineaListo(linea.id_detalle_pedido, cantidad, {
        cantidad_actual: linea.cantidad,
        cantidad_lista_actual: linea.cantidad_lista,
      });
      markListoE2e("response_received");
      if (!mountedRef.current || isStaleListoOp(opId, lineOpSeqRef.current[id])) {
        return;
      }
      const ok = resolveComanderaMutacionExito(data, { refrescarEnExito: false });
      if (ok.action === "refresh") {
        await load(true);
      } else if (ok.action === "local") {
        setLineas((prev) => reconcileListoServerLine(prev, ok.detalle));
      }
      markListoE2e("reconcile_done");
    } catch (err) {
      if (!mountedRef.current || isStaleListoOp(opId, lineOpSeqRef.current[id])) {
        return;
      }
      const fail = resolveComanderaMutacionError(err.response?.status);
      if (fail.action === "refresh") {
        setLineas((prev) => rollbackOptimisticLinea(prev, plan.rollback));
        toastError(formatApiError(err, "La comandera cambió. Se actualiza la lista."));
        await load(true);
        return;
      }
      setLineas((prev) => rollbackOptimisticLinea(prev, plan.rollback));
      toastError(formatApiError(err, "No se pudo completar la operación"));
    } finally {
      if (mountedRef.current && !isStaleListoOp(opId, lineOpSeqRef.current[id])) {
        setLineSyncing(id, false);
      }
    }
  };

  const marcar = (linea) => ejecutarMarcarListo(linea, 1);

  const marcarTodo = (linea) => ejecutarMarcarListo(linea, linea.cantidad_pendiente);

  const marcarAvisoVisto = async (idCancelacion) => {
    const key = `visto-${idCancelacion}`;
    if (procesandoRef.current) return;
    procesandoRef.current = key;
    setProcesando(key);
    try {
      await marcarCancelacionVista(idCancelacion);
      await load(true);
    } catch (err) {
      toastError(formatApiError(err, "No se pudo marcar el aviso"));
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
    <div
      className="page comandera-page"
      data-nav-shell="comandera"
      data-nav-pedidos-ready={lineas.length > 0 || !loading ? "ready" : "pending"}
    >
      <PageHeader
        title="Comandera"
        subtitle="Cronómetro desde que se confirma el pedido en ventas hasta marcar listo"
      >
        <button
          type="button"
          className="btn btn--secondary inline-flex items-center gap-2"
          onClick={() => load(true)}
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
                        className="btn btn--success btn--sm comandera-listo-btn"
                        data-nav-listo-btn={l.id_detalle_pedido}
                        onClick={() => marcar(l)}
                        disabled={lineSyncIds.has(l.id_detalle_pedido) || Boolean(procesando)}
                      >
                        {lineSyncIds.has(l.id_detalle_pedido) ? "Sincronizando…" : "1 listo"}
                      </button>
                      {l.cantidad_pendiente > 1 && (
                        <button
                          type="button"
                          className="btn btn--primary btn--sm comandera-listo-btn"
                          onClick={() => marcarTodo(l)}
                          disabled={lineSyncIds.has(l.id_detalle_pedido) || Boolean(procesando)}
                        >
                          {lineSyncIds.has(l.id_detalle_pedido) ? "Sincronizando…" : "Todo"}
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
