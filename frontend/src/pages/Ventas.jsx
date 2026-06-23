import { useEffect, useState, useMemo } from "react";
import { getProductos } from "../services/productosService";
import { getExtrasVenta } from "../services/ventasService";
import {
  getPedidosActivos,
  getPedidoMesa,
  agregarLineaPedido,
  actualizarLineaPedido,
  eliminarLineaPedido,
  cobrarPedido,
} from "../services/pedidosService";
import {
  calcularPromocion,
  getPromocionesAplicables,
} from "../services/promocionesService";
import {
  buscarClientes,
  getClientePorCodigo,
  createCliente,
  previewPuntos,
} from "../services/clientesService";
import { useAuthStore } from "../store/authStore";
import PageHeader from "../components/PageHeader";

const NUM_MESAS = 20;
const TIPO_LABEL = {
  CAFE: "Café",
  LECHE: "Leche",
  SABORIZANTE: "Saborizantes",
  OTRO: "Otros",
};

function sumExtras(extras) {
  return extras.reduce((acc, e) => acc + Number(e.precio), 0);
}

export default function Ventas() {
  const [productos, setProductos] = useState([]);
  const [extrasModal, setExtrasModal] = useState([]);
  const [cargandoExtras, setCargandoExtras] = useState(false);
  const [pedido, setPedido] = useState(null);
  const [mesasActivas, setMesasActivas] = useState({});
  const [numeroMesa, setNumeroMesa] = useState(null);
  const [formaPago, setFormaPago] = useState("EFECTIVO");
  const [loading, setLoading] = useState(false);

  const [productoModal, setProductoModal] = useState(null);
  const [extrasSeleccionados, setExtrasSeleccionados] = useState([]);
  const [promosDisponibles, setPromosDisponibles] = useState([]);
  const [promoSeleccionada, setPromoSeleccionada] = useState(null);
  const [calculoPromo, setCalculoPromo] = useState(null);
  const [cantidadModal, setCantidadModal] = useState(1);

  const [showCobroModal, setShowCobroModal] = useState(false);
  const [clienteCobro, setClienteCobro] = useState(null);
  const [busquedaCobro, setBusquedaCobro] = useState("");
  const [resultadosCobro, setResultadosCobro] = useState([]);
  const [buscandoCobro, setBuscandoCobro] = useState(false);
  const [showNuevoCliente, setShowNuevoCliente] = useState(false);
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [nuevoTelefono, setNuevoTelefono] = useState("");
  const [puntosPreviewCobro, setPuntosPreviewCobro] = useState(0);
  const [qrCobro, setQrCobro] = useState("");

  const usuario = useAuthStore((s) => s.user);

  const carrito = pedido?.lineas ?? [];

  const total = useMemo(
    () => carrito.reduce((acc, item) => acc + item.cantidad * item.precio_unitario, 0),
    [carrito]
  );

  const refrescarMesasActivas = async () => {
    try {
      const list = await getPedidosActivos();
      const map = {};
      list.forEach((p) => {
        map[p.numero_mesa] = p;
      });
      setMesasActivas(map);
    } catch (err) {
      console.error(err);
    }
  };

  const cargarPedidoMesa = async (mesa) => {
    if (!usuario?.id_usuario) return;
    try {
      const p = await getPedidoMesa(mesa, usuario.id_usuario);
      setPedido(p);
      await refrescarMesasActivas();
    } catch (err) {
      console.error(err);
      alert("Error al cargar pedido de la mesa");
    }
  };

  const seleccionarMesa = async (n) => {
    setNumeroMesa(n);
    await cargarPedidoMesa(n);
  };

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
    refrescarMesasActivas();
  }, []);

  useEffect(() => {
    if (!showCobroModal || total <= 0) {
      setPuntosPreviewCobro(0);
      return;
    }
    previewPuntos(total)
      .then((r) => setPuntosPreviewCobro(r.puntos_a_ganar))
      .catch(() => setPuntosPreviewCobro(0));
  }, [showCobroModal, total]);

  const buscarClienteCobro = async (termino) => {
    const q = termino.trim();
    if (q.length < 2) {
      setResultadosCobro([]);
      return;
    }
    try {
      setBuscandoCobro(true);
      const data = await buscarClientes(q);
      setResultadosCobro(data.resultados || []);
    } catch (err) {
      console.error(err);
    } finally {
      setBuscandoCobro(false);
    }
  };

  useEffect(() => {
    if (!showCobroModal) return;
    const t = setTimeout(() => buscarClienteCobro(busquedaCobro), 300);
    return () => clearTimeout(t);
  }, [busquedaCobro, showCobroModal]);

  const seleccionarClienteCobro = (c) => {
    setClienteCobro(c);
    setBusquedaCobro("");
    setResultadosCobro([]);
  };

  const resolverQrCobro = async (codigo) => {
    const c = codigo.trim().toUpperCase();
    if (!c.startsWith("CAFE-")) return;
    try {
      const cliente = await getClientePorCodigo(c);
      seleccionarClienteCobro(cliente);
      setQrCobro("");
    } catch (err) {
      alert(err.response?.data?.detail || "Código no encontrado");
      setQrCobro("");
    }
  };

  const guardarNuevoCliente = async () => {
    try {
      const c = await createCliente({ nombre: nuevoNombre, telefono: nuevoTelefono });
      seleccionarClienteCobro(c);
      setShowNuevoCliente(false);
      setNuevoNombre("");
      setNuevoTelefono("");
    } catch (err) {
      alert(err.response?.data?.detail || "Error al registrar cliente");
    }
  };

  const abrirCobroModal = () => {
    if (!pedido?.id_pedido || carrito.length === 0) return;
    setClienteCobro(null);
    setBusquedaCobro("");
    setResultadosCobro([]);
    setQrCobro("");
    setShowCobroModal(true);
  };

  const cerrarCobroModal = () => {
    setShowCobroModal(false);
    setClienteCobro(null);
    setBusquedaCobro("");
    setResultadosCobro([]);
    setQrCobro("");
  };

  const extrasPorTipo = useMemo(() => {
    const grupos = {};
    for (const e of extrasModal) {
      const t = e.tipo || "OTRO";
      if (!grupos[t]) grupos[t] = [];
      grupos[t].push(e);
    }
    return grupos;
  }, [extrasModal]);

  const recalcularPromoModal = async (producto, idPromo, extras, cantidad) => {
    if (!producto) return;
    try {
      const calc = await calcularPromocion({
        id_producto: producto.id_producto,
        id_promocion: idPromo || null,
        cantidad,
        precio_extras: sumExtras(extras),
      });
      setCalculoPromo(calc);
    } catch (err) {
      console.error(err);
      setCalculoPromo(null);
    }
  };

  useEffect(() => {
    if (!productoModal) return;
    recalcularPromoModal(
      productoModal,
      promoSeleccionada,
      extrasSeleccionados,
      cantidadModal
    );
  }, [productoModal, promoSeleccionada, extrasSeleccionados, cantidadModal]);

  const abrirModalProducto = async (producto) => {
    if (!numeroMesa) {
      alert("Primero selecciona el número de mesa");
      return;
    }
    setProductoModal(producto);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
    setPromosDisponibles([]);
    setPromoSeleccionada(null);
    setCalculoPromo(null);
    setCantidadModal(1);
    try {
      setCargandoExtras(true);
      const [extras, promos] = await Promise.all([
        getExtrasVenta(producto.id_producto),
        getPromocionesAplicables(producto.id_producto),
      ]);
      setExtrasModal(extras);
      setPromosDisponibles(promos);
      if (promos.length > 0) {
        setPromoSeleccionada(promos[0].id_promocion);
      }
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

  const confirmarAgregarAlCarrito = async () => {
    if (!productoModal || !calculoPromo || !numeroMesa || !usuario?.id_usuario) return;
    if (!calculoPromo.margen_ok) {
      alert(calculoPromo.mensaje || "La promoción no cumple el margen mínimo");
      return;
    }

    try {
      setLoading(true);
      await agregarLineaPedido(numeroMesa, usuario.id_usuario, {
        id_producto: productoModal.id_producto,
        cantidad: cantidadModal,
        precio_unitario: Number(calculoPromo.precio_unitario),
        precio_original: Number(calculoPromo.precio_original_unitario),
        id_promocion: calculoPromo.id_promocion,
        extras: extrasSeleccionados,
        enviar_comanda: true,
      });
      await cargarPedidoMesa(numeroMesa);
    } catch (err) {
      alert(err.response?.data?.detail || "Error al agregar al pedido");
      return;
    } finally {
      setLoading(false);
    }

    setProductoModal(null);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
    setPromosDisponibles([]);
    setPromoSeleccionada(null);
    setCalculoPromo(null);
    setCantidadModal(1);
  };

  const cambiarCantidad = async (idDetalle, value) => {
    const cant = parseInt(value, 10);
    if (isNaN(cant) || cant < 1 || !numeroMesa) return;
    try {
      await actualizarLineaPedido(idDetalle, { cantidad: cant });
      await cargarPedidoMesa(numeroMesa);
    } catch (err) {
      alert(err.response?.data?.detail || "Error al actualizar cantidad");
    }
  };

  const eliminarDelCarrito = async (idDetalle) => {
    if (!numeroMesa) return;
    try {
      await eliminarLineaPedido(idDetalle);
      await cargarPedidoMesa(numeroMesa);
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar línea");
    }
  };

  const ejecutarCobro = async (conCliente) => {
    if (!usuario?.id_usuario || !pedido?.id_pedido) return;

    try {
      setLoading(true);
      const res = await cobrarPedido(pedido.id_pedido, {
        id_usuario: usuario.id_usuario,
        forma_pago: formaPago,
        id_cliente: conCliente && clienteCobro ? clienteCobro.id_cliente : null,
      });
      let msg = `Cuenta cerrada. Mesa ${res.numero_mesa} — Folio: ${res.id_venta}\nTotal: $${Number(res.total).toFixed(2)}`;
      if (res.puntos_generados > 0) {
        msg += `\n\n+${res.puntos_generados} pts → ${res.cliente_nombre}\nNuevo saldo: ${res.cliente_puntos_saldo} pts`;
      }
      alert(msg);
      cerrarCobroModal();
      setPedido(null);
      setNumeroMesa(null);
      await refrescarMesasActivas();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Error al cobrar");
    } finally {
      setLoading(false);
    }
  };

  const precioPreview = calculoPromo ? Number(calculoPromo.precio_unitario) : 0;

  return (
    <div className="page">
      <PageHeader
        title="Punto de venta"
        subtitle="Pedidos por mesa — al cobrar puedes asignar cliente y puntos"
      />

      <section className="section">
        <h2>1. Selecciona la mesa</h2>
        <p className="hint">Cada mesa mantiene su pedido abierto. Puedes cambiar de mesa sin perder nada.</p>
        <div className="mesa-grid">
          {Array.from({ length: NUM_MESAS }, (_, i) => i + 1).map((n) => {
            const activa = mesasActivas[n];
            return (
              <button
                key={n}
                type="button"
                onClick={() => seleccionarMesa(n)}
                className={`mesa-btn ${numeroMesa === n ? "mesa-btn--active" : ""} ${activa ? "mesa-btn--ocupada" : ""}`}
              >
                {n}
                {activa && activa.num_lineas > 0 && (
                  <span className="mesa-btn__badge">{activa.num_lineas}</span>
                )}
              </button>
            );
          })}
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
          <h2>Pedido {numeroMesa ? `(Mesa ${numeroMesa})` : ""}</h2>
          {carrito.length === 0 ? (
            <p className="empty-state">Sin productos en esta mesa</p>
          ) : (
            <>
              {carrito.map((item) => (
                <div key={item.id_detalle_pedido} className="cart-item">
                  <div style={{ flex: 1 }}>
                    <strong>{item.nombre_producto}</strong>
                    {item.nombre_promocion && (
                      <span className="badge" style={{ marginLeft: "0.35rem" }}>
                        {item.nombre_promocion}
                      </span>
                    )}
                    {item.cantidad_pendiente > 0 && item.en_comanda && (
                      <span className="badge badge--kitchen" style={{ marginLeft: "0.35rem" }}>
                        en comanda
                      </span>
                    )}
                    {item.extras?.length > 0 && (
                      <ul className="cart-item__extras">
                        {item.extras.map((e) => (
                          <li key={e.id_extra}>
                            + {e.nombre} (${Number(e.precio).toFixed(2)})
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="hint" style={{ marginTop: "0.25rem" }}>
                      {(item.descuento_unitario ?? 0) > 0 ? (
                        <>
                          <s>${Number(item.precio_original).toFixed(2)}</s> → $
                          {Number(item.precio_unitario).toFixed(2)} c/u
                        </>
                      ) : (
                        <>${Number(item.precio_unitario).toFixed(2)} c/u</>
                      )}
                    </div>
                  </div>
                  <input
                    type="number"
                    min="1"
                    value={item.cantidad}
                    onChange={(e) => cambiarCantidad(item.id_detalle_pedido, e.target.value)}
                    style={{ width: 56 }}
                    className="input"
                  />
                  <span style={{ minWidth: 72, fontWeight: 600 }}>
                    ${(item.cantidad * item.precio_unitario).toFixed(2)}
                  </span>
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={() => eliminarDelCarrito(item.id_detalle_pedido)}
                    aria-label="Quitar"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </>
          )}

          <div className="cart-total">Total: ${total.toFixed(2)}</div>
          <button
            type="button"
            className="btn btn--success"
            style={{ width: "100%", marginTop: "0.75rem", padding: "0.75rem" }}
            onClick={abrirCobroModal}
            disabled={loading || carrito.length === 0 || !numeroMesa}
          >
            Cerrar cuenta / Cobrar
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
            {!cargandoExtras && promosDisponibles.length > 0 && (
              <div style={{ marginBottom: "1rem" }}>
                <label className="hint">Promoción</label>
                <select
                  className="select"
                  value={promoSeleccionada || ""}
                  onChange={(e) =>
                    setPromoSeleccionada(e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">Sin promoción</option>
                  {promosDisponibles.map((p) => (
                    <option key={p.id_promocion} value={p.id_promocion}>
                      {p.nombre} ({p.tipo === "PORCENTAJE" ? `${p.valor}%` : p.tipo})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="form-row" style={{ marginBottom: "1rem" }}>
              <label>Cantidad</label>
              <input
                type="number"
                min="1"
                value={cantidadModal}
                onChange={(e) => setCantidadModal(Math.max(1, parseInt(e.target.value, 10) || 1))}
                className="input"
                style={{ width: 80 }}
              />
            </div>

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

            {!cargandoExtras && calculoPromo && (
              <div className="price-preview">
                {calculoPromo.descuento_unitario > 0 ? (
                  <>
                    <s>${Number(calculoPromo.precio_original_unitario).toFixed(2)}</s>{" "}
                    <strong>${precioPreview.toFixed(2)}</strong> c/u
                    {calculoPromo.margen_porcentaje != null && (
                      <span className="hint"> · Margen {calculoPromo.margen_porcentaje}%</span>
                    )}
                    {!calculoPromo.margen_ok && (
                      <p style={{ color: "var(--color-danger, #c0392b)" }}>
                        {calculoPromo.mensaje}
                      </p>
                    )}
                  </>
                ) : (
                  <>Precio unitario: ${precioPreview.toFixed(2)}</>
                )}
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
              <button
                type="button"
                className="btn btn--primary"
                onClick={confirmarAgregarAlCarrito}
                disabled={!calculoPromo || !calculoPromo.margen_ok}
              >
                Agregar y enviar a comanda
              </button>
            </div>
          </div>
        </div>
      )}

      {showCobroModal && (
        <div className="modal-overlay" onClick={cerrarCobroModal}>
          <div className="modal-box modal-box--wide" onClick={(e) => e.stopPropagation()}>
            <h2>Cerrar cuenta — Mesa {numeroMesa}</h2>
            <p className="cart-total" style={{ margin: "0.5rem 0 1rem" }}>
              Total: ${total.toFixed(2)}
            </p>

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

            <hr style={{ border: "none", borderTop: "1px solid var(--cream-dark)", margin: "1.25rem 0" }} />

            <h3 style={{ marginTop: 0, fontSize: "1.05rem" }}>¿Cliente frecuente? (puntos)</h3>
            <p className="hint">Opcional — busca por teléfono, nombre o escanea QR</p>

            {clienteCobro ? (
              <div className="cliente-seleccionado card" style={{ marginBottom: "1rem" }}>
                <div>
                  <strong>{clienteCobro.nombre}</strong>
                  <span className="hint"> · {clienteCobro.telefono}</span>
                  <br />
                  <span className="badge">Saldo: {clienteCobro.puntos_saldo} pts</span>
                  {puntosPreviewCobro > 0 && (
                    <span className="hint" style={{ marginLeft: "0.5rem" }}>
                      → <strong>+{puntosPreviewCobro} pts</strong> en esta cuenta
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn--secondary btn--sm"
                  onClick={() => setClienteCobro(null)}
                >
                  Cambiar
                </button>
              </div>
            ) : (
              <>
                <div className="cliente-busqueda">
                  <input
                    className="input"
                    placeholder="Teléfono o nombre…"
                    value={busquedaCobro}
                    onChange={(e) => setBusquedaCobro(e.target.value)}
                    autoFocus
                  />
                  <input
                    className="input cliente-qr-input"
                    placeholder="QR CAFE-…"
                    value={qrCobro}
                    onChange={(e) => {
                      const v = e.target.value;
                      setQrCobro(v);
                      if (v.toUpperCase().startsWith("CAFE-") && v.length >= 10) {
                        resolverQrCobro(v);
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") resolverQrCobro(qrCobro);
                    }}
                  />
                  <button
                    type="button"
                    className="btn btn--secondary btn--sm"
                    onClick={() => setShowNuevoCliente(true)}
                  >
                    + Nuevo
                  </button>
                </div>
                {buscandoCobro && <p className="hint">Buscando…</p>}
                {resultadosCobro.length > 0 && (
                  <ul className="cliente-resultados">
                    {resultadosCobro.map((c) => (
                      <li key={c.id_cliente}>
                        <button
                          type="button"
                          className="cliente-resultado-btn"
                          onClick={() => seleccionarClienteCobro(c)}
                        >
                          {c.nombre} · {c.telefono} · {c.puntos_saldo} pts
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}

            <div className="modal-footer" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
              <button type="button" className="btn btn--secondary" onClick={cerrarCobroModal} disabled={loading}>
                Cancelar
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => ejecutarCobro(false)}
                disabled={loading}
              >
                Cobrar sin cliente
              </button>
              <button
                type="button"
                className="btn btn--success"
                onClick={() => ejecutarCobro(true)}
                disabled={loading || !clienteCobro}
              >
                {loading
                  ? "Procesando…"
                  : clienteCobro
                    ? puntosPreviewCobro > 0
                      ? `Cobrar y sumar ${puntosPreviewCobro} pts`
                      : "Cobrar con cliente"
                    : "Selecciona un cliente"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showNuevoCliente && (
        <div className="modal-overlay" onClick={() => setShowNuevoCliente(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h2>Registrar cliente</h2>
            <div className="form-row">
              <label>Nombre</label>
              <input className="input" value={nuevoNombre} onChange={(e) => setNuevoNombre(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Teléfono</label>
              <input className="input" value={nuevoTelefono} onChange={(e) => setNuevoTelefono(e.target.value)} />
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn--secondary" onClick={() => setShowNuevoCliente(false)}>
                Cancelar
              </button>
              <button type="button" className="btn btn--primary" onClick={guardarNuevoCliente}>
                Registrar y usar en cobro
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
