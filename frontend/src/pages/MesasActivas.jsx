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

  const cargar = useCallback(async () => {
    try {
      const data = await getPedidosActivos();
      setPedidos(data.sort((a, b) => a.numero_mesa - b.numero_mesa));
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

  return (
    <div>
      <PageHeader
        title="Mesas activas"
        subtitle="Pedidos abiertos con tiempo en mesa y estado de comanda"
      />

      <div style={{ marginBottom: "1rem" }}>
        <button type="button" className="btn btn--secondary btn--sm" onClick={cargar}>
          Actualizar
        </button>
      </div>

      {pedidos.length === 0 ? (
        <p className="empty-state">No hay mesas con pedido activo en este momento.</p>
      ) : (
        <div className="grid-stats" style={{ alignItems: "stretch" }}>
          {pedidos.map((p) => (
            <div key={p.id_pedido} className="card" style={{ margin: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <h3 style={{ margin: 0 }}>
                  {p.para_llevar ? "Para llevar" : `Mesa ${p.numero_mesa}`}
                </h3>
                <strong>{fmt(p.total)}</strong>
              </div>
              <p className="hint" style={{ margin: "0.35rem 0 0.75rem" }}>
                Pedido #{p.id_pedido}
                {p.cliente_nombre && <> · {p.cliente_nombre}</>}
                {" · "}
                {p.num_lineas} línea(s)
                {p.pendientes_comanda > 0 && (
                  <> · {p.pendientes_comanda} en cocina</>
                )}
              </p>
              <p className="hint" style={{ marginBottom: "0.75rem" }}>
                Tiempo en mesa:{" "}
                {p.fecha_apertura ? (
                  <ElapsedTimer since={p.fecha_apertura} />
                ) : (
                  formatDuration(p.segundos_activa || 0)
                )}
              </p>

              <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.9rem" }}>
                {p.lineas?.map((l) => (
                  <li key={l.id_detalle_pedido} style={{ marginBottom: "0.35rem" }}>
                    {l.nombre_producto} × {l.cantidad}
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

              <div style={{ marginTop: "0.75rem" }}>
                <Link
                  to={p.para_llevar ? "/ventas-para-llevar" : "/ventas"}
                  className="btn btn--ghost btn--sm"
                >
                  Ir a ventas
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
