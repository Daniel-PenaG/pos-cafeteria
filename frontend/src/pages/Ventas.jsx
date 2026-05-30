import { useEffect, useState, useMemo } from "react";
import { getProductos } from "../services/productosService";
import { crearVenta, getExtrasVenta } from "../services/ventasService";
import { useAuthStore } from "../store/authStore";
import PageHeader from "../components/PageHeader";

const NUM_MESAS = 20;
const TIPO_LABEL = {
  CAFE: "Café",
  LECHE: "Leche",
  SABORIZANTE: "Saborizantes",
  OTRO: "Otros",
};

function lineKey(idProducto, extras) {
  const ids = extras.map((e) => e.id_extra).sort((a, b) => a - b).join("-");
  return `${idProducto}-${ids}`;
}

function sumExtras(extras) {
  return extras.reduce((acc, e) => acc + Number(e.precio), 0);
}

export default function Ventas() {
  const [productos, setProductos] = useState([]);
  const [extrasModal, setExtrasModal] = useState([]);
  const [cargandoExtras, setCargandoExtras] = useState(false);
  const [carrito, setCarrito] = useState([]);
  const [numeroMesa, setNumeroMesa] = useState(null);
  const [formaPago, setFormaPago] = useState("EFECTIVO");
  const [loading, setLoading] = useState(false);

  const [productoModal, setProductoModal] = useState(null);
  const [extrasSeleccionados, setExtrasSeleccionados] = useState([]);

  const usuario = useAuthStore((s) => s.user);

  useEffect(() => {
    const load = async () => {
      try {
        const prods = await getProductos();
        setProductos(
          prods
            .filter((p) => p.activo !== false)
            .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
        );
      } catch (err) {
        console.error(err);
        alert("Error al cargar productos");
      }
    };
    load();
  }, []);

  const extrasPorTipo = useMemo(() => {
    const grupos = {};
    for (const e of extrasModal) {
      const t = e.tipo || "OTRO";
      if (!grupos[t]) grupos[t] = [];
      grupos[t].push(e);
    }
    return grupos;
  }, [extrasModal]);

  const abrirModalProducto = async (producto) => {
    if (!numeroMesa) {
      alert("Primero selecciona el número de mesa");
      return;
    }
    setProductoModal(producto);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
    try {
      setCargandoExtras(true);
      const extras = await getExtrasVenta(producto.id_producto);
      setExtrasModal(extras);
    } catch (err) {
      console.error(err);
      alert("Error al cargar extras del producto");
      return;
    } finally {
      setCargandoExtras(false);
    }
  };

  const toggleExtra = (extra) => {
    setExtrasSeleccionados((prev) => {
      const existe = prev.find((e) => e.id_extra === extra.id_extra);
      if (existe) {
        return prev.filter((e) => e.id_extra !== extra.id_extra);
      }
      return [
        ...prev,
        {
          id_extra: extra.id_extra,
          nombre: extra.nombre,
          precio: Number(extra.precio),
        },
      ];
    });
  };

  const confirmarAgregarAlCarrito = () => {
    if (!productoModal) return;

    const precioBase = Number(productoModal.precio_venta);
    const precioExtras = sumExtras(extrasSeleccionados);
    const precioUnitario = precioBase + precioExtras;
    const key = lineKey(productoModal.id_producto, extrasSeleccionados);

    setCarrito((prev) => {
      const existe = prev.find((p) => p.lineKey === key);
      if (existe) {
        return prev.map((p) =>
          p.lineKey === key ? { ...p, cantidad: p.cantidad + 1 } : p
        );
      }
      return [
        ...prev,
        {
          lineKey: key,
          id_producto: productoModal.id_producto,
          nombre: productoModal.nombre,
          precio_base: precioBase,
          precio_unitario: precioUnitario,
          cantidad: 1,
          extras: [...extrasSeleccionados],
        },
      ];
    });

    setProductoModal(null);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
  };

  const cambiarCantidad = (key, value) => {
    const cant = parseInt(value, 10);
    if (isNaN(cant) || cant < 1) return;
    setCarrito((prev) =>
      prev.map((p) => (p.lineKey === key ? { ...p, cantidad: cant } : p))
    );
  };

  const eliminarDelCarrito = (key) => {
    setCarrito((prev) => prev.filter((p) => p.lineKey !== key));
  };

  const total = carrito.reduce(
    (acc, item) => acc + item.cantidad * item.precio_unitario,
    0
  );

  const handleVenta = async () => {
    if (!usuario?.id_usuario) {
      alert("Sesión inválida");
      return;
    }
    if (carrito.length === 0) return;

    const payload = {
      id_usuario: usuario.id_usuario,
      numero_mesa: numeroMesa,
      forma_pago: formaPago,
      detalles: carrito.map((item) => ({
        id_producto: item.id_producto,
        cantidad: item.cantidad,
        precio_unitario: item.precio_unitario,
        extras: item.extras,
      })),
    };

    try {
      setLoading(true);
      const res = await crearVenta(payload);
      alert(`Venta registrada. Mesa ${res.numero_mesa} — Folio: ${res.id_venta}`);
      setCarrito([]);
      setNumeroMesa(null);
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Error al registrar la venta");
    } finally {
      setLoading(false);
    }
  };

  const precioPreview =
    productoModal &&
    Number(productoModal.precio_venta) + sumExtras(extrasSeleccionados);

  return (
    <div className="page">
      <PageHeader
        title="Punto de venta"
        subtitle="Selecciona mesa, agrega productos y personaliza con extras"
      />

      <section className="section">
        <h2>1. Selecciona la mesa</h2>
        <p className="hint">Elige la mesa antes de agregar productos al pedido.</p>
        <div className="mesa-grid">
          {Array.from({ length: NUM_MESAS }, (_, i) => i + 1).map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setNumeroMesa(n)}
              className={`mesa-btn ${numeroMesa === n ? "mesa-btn--active" : ""}`}
            >
              {n}
            </button>
          ))}
        </div>
        {numeroMesa && (
          <p className="mesa-selected">Mesa {numeroMesa} seleccionada</p>
        )}
      </section>

      <div className={`ventas-layout ${!numeroMesa ? "ventas-layout--disabled" : ""}`}>
        <div>
          <h2>2. Productos</h2>
          {!numeroMesa && (
            <p className="hint">Selecciona una mesa para habilitar productos</p>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Precio base</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {productos.map((p) => (
                  <tr key={p.id_producto}>
                    <td>{p.nombre}</td>
                    <td>${Number(p.precio_venta).toFixed(2)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--primary btn--sm"
                        onClick={() => abrirModalProducto(p)}
                      >
                        Agregar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="cart-panel">
          <h2>Carrito {numeroMesa ? `(Mesa ${numeroMesa})` : ""}</h2>
          {carrito.length === 0 ? (
            <p className="empty-state">El carrito está vacío</p>
          ) : (
            <>
              {carrito.map((item) => (
                <div key={item.lineKey} className="cart-item">
                  <div style={{ flex: 1 }}>
                    <strong>{item.nombre}</strong>
                    {item.extras.length > 0 && (
                      <ul className="cart-item__extras">
                        {item.extras.map((e) => (
                          <li key={e.id_extra}>
                            + {e.nombre} (${Number(e.precio).toFixed(2)})
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="hint" style={{ marginTop: "0.25rem" }}>
                      Base ${item.precio_base.toFixed(2)} → $
                      {item.precio_unitario.toFixed(2)} c/u
                    </div>
                  </div>
                  <input
                    type="number"
                    min="1"
                    value={item.cantidad}
                    onChange={(e) => cambiarCantidad(item.lineKey, e.target.value)}
                    style={{ width: 56 }}
                    className="input"
                  />
                  <span style={{ minWidth: 72, fontWeight: 600 }}>
                    ${(item.cantidad * item.precio_unitario).toFixed(2)}
                  </span>
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={() => eliminarDelCarrito(item.lineKey)}
                    aria-label="Quitar"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </>
          )}

          <div className="cart-total">Total: ${total.toFixed(2)}</div>
          <div className="form-row">
            <label>Forma de pago</label>
            <select
              className="select"
              value={formaPago}
              onChange={(e) => setFormaPago(e.target.value)}
            >
              <option value="EFECTIVO">Efectivo</option>
              <option value="TARJETA">Tarjeta</option>
              <option value="TRANSFERENCIA">Transferencia</option>
            </select>
          </div>
          <button
            type="button"
            className="btn btn--success"
            style={{ width: "100%", marginTop: "0.5rem", padding: "0.75rem" }}
            onClick={handleVenta}
            disabled={loading || carrito.length === 0 || !numeroMesa}
          >
            {loading ? "Guardando…" : "Registrar venta"}
          </button>
        </div>
      </div>

      {productoModal && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h2>{productoModal.nombre}</h2>
            <p className="hint">
              Precio base ${Number(productoModal.precio_venta).toFixed(2)} · Mesa {numeroMesa}
            </p>
            <p style={{ fontSize: "0.9rem" }}>Extras opcionales:</p>

            {cargandoExtras && <p className="hint">Cargando extras…</p>}
            {!cargandoExtras && extrasModal.length === 0 && (
              <p className="empty-state" style={{ textAlign: "left", padding: "0.5rem 0" }}>
                Sin extras para esta categoría. Configúralos en Extras de venta.
              </p>
            )}

            {!cargandoExtras &&
              Object.entries(extrasPorTipo).map(([tipo, lista]) => (
                <div key={tipo} style={{ marginBottom: "1rem" }}>
                  <div style={{ fontWeight: 600, marginBottom: "0.4rem", fontSize: "0.85rem" }}>
                    {TIPO_LABEL[tipo] || tipo}
                  </div>
                  <div className="extra-chips">
                    {lista.map((extra) => {
                    const sel = extrasSeleccionados.some(
                      (e) => e.id_extra === extra.id_extra
                    );
                    return (
                      <button
                        key={extra.id_extra}
                          type="button"
                          onClick={() => toggleExtra(extra)}
                          className={`extra-chip ${sel ? "extra-chip--selected" : ""}`}
                        >
                          {extra.nombre} (+${Number(extra.precio).toFixed(2)})
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}

            {!cargandoExtras && (
              <div className="price-preview">
                Precio unitario: ${precioPreview.toFixed(2)}
              </div>
            )}

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  setProductoModal(null);
                  setExtrasSeleccionados([]);
                  setExtrasModal([]);
                }}
              >
                Cancelar
              </button>
              <button type="button" className="btn btn--primary" onClick={confirmarAgregarAlCarrito}>
                Agregar al carrito
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
