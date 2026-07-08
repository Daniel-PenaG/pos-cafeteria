import { useEffect, useState } from "react";
import { getInsumos } from "../services/insumosService";
import { crearCompra } from "../services/comprasService";
import PageHeader from "../components/PageHeader";

export default function Compras() {
  const [insumos, setInsumos] = useState([]);
  const [carrito, setCarrito] = useState([]);
  const [proveedor, setProveedor] = useState("");

  useEffect(() => {
    const load = async () => {
      const data = await getInsumos();
      setInsumos(data);
    };
    load();
  }, []);

  const agregar = (insumo) => {
    setCarrito((prev) => [
      ...prev,
      {
        id_insumo: insumo.id_insumo,
        nombre: insumo.nombre,
        cantidad: 1,
        costo_unitario: 1,
      },
    ]);
  };

  const registrar = async () => {
    if (!proveedor) return alert("Ingresa proveedor");
    if (carrito.length === 0) return alert("Agrega insumos");

    const payload = {
      proveedor,
      detalles: carrito.map((i) => ({
        id_insumo: i.id_insumo,
        cantidad: i.cantidad,
        costo_unitario: i.costo_unitario,
      })),
    };

    const res = await crearCompra(payload);
    alert(`Compra registrada. Folio: ${res.id_compra}`);
    setCarrito([]);
    setProveedor("");
  };

  return (
    <div className="page">
      <PageHeader
        title="Compras"
        subtitle="Reabastecimiento de insumos con proveedor"
      />

      <p className="hint" style={{ marginTop: 0, marginBottom: "1rem" }}>
        Las compras registradas suman al stock de <strong>bodega</strong>. Surtir a cafetería desde Insumos.
      </p>

      <section className="section" style={{ marginBottom: "1.5rem" }}>
        <div className="form-row" style={{ maxWidth: 400 }}>
          <label>Proveedor</label>
          <input
            placeholder="Nombre del proveedor"
            value={proveedor}
            onChange={(e) => setProveedor(e.target.value)}
          />
        </div>
      </section>

      <div className="ventas-layout">
        <section className="card">
          <h2>Insumos disponibles</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Insumo</th>
                  <th>Bodega</th>
                  <th>Cafetería</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {insumos.map((i) => (
                  <tr key={i.id_insumo}>
                    <td>{i.nombre}</td>
                    <td>{Number(i.stock_bodega ?? 0)}</td>
                    <td>{Number(i.stock_cafeteria ?? 0)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--primary btn--sm"
                        onClick={() => agregar(i)}
                      >
                        Agregar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="cart-panel">
          <h2>Carrito de compra</h2>
          {carrito.length === 0 ? (
            <p className="empty-state">Sin insumos en el carrito</p>
          ) : (
            carrito.map((i, idx) => (
              <div key={idx} className="cart-item">
                <div style={{ flex: 1 }}>
                  <strong>{i.nombre}</strong>
                  <div className="form-grid" style={{ marginTop: "0.5rem", gap: "0.5rem" }}>
                    <div>
                      <label className="hint">Cantidad</label>
                      <input
                        type="number"
                        min="1"
                        value={i.cantidad}
                        onChange={(e) =>
                          setCarrito((prev) =>
                            prev.map((x, j) =>
                              j === idx ? { ...x, cantidad: Number(e.target.value) } : x
                            )
                          )
                        }
                      />
                    </div>
                    <div>
                      <label className="hint">Costo unit.</label>
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={i.costo_unitario}
                        onChange={(e) =>
                          setCarrito((prev) =>
                            prev.map((x, j) =>
                              j === idx
                                ? { ...x, costo_unitario: Number(e.target.value) }
                                : x
                            )
                          )
                        }
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
          <button
            type="button"
            className="btn btn--success"
            style={{ width: "100%", marginTop: "1rem" }}
            onClick={registrar}
            disabled={carrito.length === 0}
          >
            Registrar compra
          </button>
        </section>
      </div>
    </div>
  );
}
