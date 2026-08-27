import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import ElapsedTimer from "../components/ElapsedTimer";
import { getPedidosActivos } from "../services/pedidosService";
import { formatDuration } from "../utils/formatDuration";

function fmt(n) {
  return `$${Number(n).toFixed(2)}`;
}

export default function MesasActivas() {
  const [pedidos, setPedidos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [seleccionado, setSeleccionado] = useState(null);

  const cargar = useCallback(async () => {
    try {
      const data = await getPedidosActivos();
      const ordenados = data.sort((a, b) => a.numero_mesa - b.numero_mesa);
      setPedidos(ordenados);
      setSeleccionado((prev) => {
        if (!ordenados.length) return null;
        if (prev && ordenados.some((p) => p.id_pedido === prev.id_pedido)) {
          return ordenados.find((p) => p.id_pedido === prev.id_pedido);
        }
        return ordenados[0];
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, 30000);
    return () => clearInterval(id);
  }, [cargar]);

  if (loading) return <div className="loading-state">Cargando mesas…</div>;

  const ventasUrl = seleccionado?.para_llevar
    ? "/ventas-para-llevar"
    : `/ventas?mesa=${seleccionado?.numero_mesa ?? ""}`;

  return (
    <div>
      <PageHeader
        title="Mesas activas"
        subtitle="Selecciona una mesa para ver el tiempo en uso y abrir ventas"
      />

      <div style={{ marginBottom: "1rem" }}>
        <button type="button" className="btn btn--secondary btn--sm" onClick={cargar}>
          Actualizar
        </button>
      </div>

      {pedidos.length === 0 ? (
        <p className="empty-state">No hay mesas con pedido activo en este momento.</p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(200px, 280px) 1fr",
            gap: "1rem",
            alignItems: "start",
          }}
        >
          <div className="card" style={{ margin: 0, padding: "0.5rem" }}>
            <p className="hint" style={{ margin: "0.25rem 0.5rem 0.75rem" }}>
              Mesas en uso
            </p>
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {pedidos.map((p) => {
                const activa = seleccionado?.id_pedido === p.id_pedido;
                return (
                  <li key={p.id_pedido}>
                    <button
                      type="button"
                      onClick={() => setSeleccionado(p)}
                      className="btn btn--ghost"
                      style={{
                        width: "100%",
                        justifyContent: "space-between",
                        marginBottom: "0.35rem",
                        fontWeight: activa ? 600 : 400,
                        background: activa ? "var(--surface-2, #f0f4f8)" : undefined,
                      }}
                    >
                      <span>
                        {p.para_llevar ? "Para llevar" : `Mesa ${p.numero_mesa}`}
                      </span>
                      <span>{fmt(p.total)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          {seleccionado && (
            <div className="card" style={{ margin: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <h3 style={{ margin: 0 }}>
                  {seleccionado.para_llevar
                    ? "Para llevar"
                    : `Mesa ${seleccionado.numero_mesa}`}
                </h3>
                <strong>{fmt(seleccionado.total)}</strong>
              </div>

              <div
                style={{
                  margin: "1rem 0",
                  padding: "1rem",
                  textAlign: "center",
                  borderRadius: "8px",
                  background: "var(--surface-2, #f0f4f8)",
                }}
              >
                <p className="hint" style={{ margin: "0 0 0.35rem" }}>
                  Tiempo en mesa
                </p>
                <p style={{ margin: 0, fontSize: "1.75rem", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                  {seleccionado.fecha_apertura ? (
                    <ElapsedTimer since={seleccionado.fecha_apertura} />
                  ) : (
                    formatDuration(seleccionado.segundos_activa || 0)
                  )}
                </p>
              </div>

              <p className="hint" style={{ margin: "0 0 0.75rem" }}>
                Pedido #{seleccionado.id_pedido}
                {seleccionado.cliente_nombre && <> · {seleccionado.cliente_nombre}</>}
                {" · "}
                {seleccionado.num_lineas} línea(s)
                {seleccionado.pendientes_comanda > 0 && (
                  <> · {seleccionado.pendientes_comanda} en cocina</>
                )}
              </p>

              <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.9rem" }}>
                {seleccionado.lineas?.map((l) => (
                  <li key={l.id_detalle_pedido} style={{ marginBottom: "0.35rem" }}>
                    {l.nombre_producto} × {l.cantidad}
                    {l.nombre_promocion && (
                      <span className="badge badge--ok" style={{ marginLeft: "0.35rem" }}>
                        {l.nombre_promocion}
                      </span>
                    )}
                    {!l.en_comanda && (
                      <span className="badge badge--pending" style={{ marginLeft: "0.35rem" }}>
                        sin confirmar
                      </span>
                    )}
                    {l.en_comanda && l.cantidad_pendiente > 0 && l.fecha_envio_comanda && (
                      <span style={{ marginLeft: "0.35rem" }}>
                        <ElapsedTimer since={l.fecha_envio_comanda} className="text-sm" />
                      </span>
                    )}
                    {l.en_comanda && l.cantidad_pendiente === 0 && (
                      <span className="badge badge--ok" style={{ marginLeft: "0.35rem" }}>
                        listo
                      </span>
                    )}
                  </li>
                ))}
              </ul>

              <div style={{ marginTop: "1rem" }}>
                <Link to={ventasUrl} className="btn btn--primary btn--sm">
                  Abrir ventas de esta mesa
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
