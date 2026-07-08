import { useEffect, useState } from "react";
import {
  getInsumos,
  createInsumo,
  updateInsumo,
  deleteInsumo,
  traspasarInsumo,
} from "../services/insumosService";
import PageHeader from "../components/PageHeader";

const UNIDADES = [
  { value: "g", label: "Gramos (g)" },
  { value: "kg", label: "Kilogramos (kg)" },
  { value: "ml", label: "Mililitros (ml)" },
  { value: "L", label: "Litros (L)" },
  { value: "pz", label: "Pieza (pz)" },
  { value: "unidad", label: "Unidad" },
  { value: "taza", label: "Taza" },
  { value: "cda", label: "Cucharada (cda)" },
  { value: "cdta", label: "Cucharadita (cdta)" },
];
const UNIDAD_VALUES = UNIDADES.map((u) => u.value);
const UNIDAD_OTRA = "__otra__";
const MARGEN_INSUMO = 0.1;

function calcularCostoDesdeCompra(precioTotal, cantidad) {
  const total = Number(precioTotal);
  const cant = Number(cantidad);
  if (!total || total <= 0 || !cant || cant <= 0) return null;
  const totalConMargen = total * (1 + MARGEN_INSUMO);
  return totalConMargen / cant;
}

function stockTotal(insumo) {
  return Number(insumo.stock_actual ?? 0);
}

export default function Insumos() {
  const [insumos, setInsumos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [showTraspaso, setShowTraspaso] = useState(false);
  const [editing, setEditing] = useState(null);
  const [traspasoInsumo, setTraspasoInsumo] = useState(null);
  const [traspasoCantidad, setTraspasoCantidad] = useState("");

  const [nombre, setNombre] = useState("");
  const [unidad, setUnidad] = useState("g");
  const [unidadOtra, setUnidadOtra] = useState("");
  const [stockBodega, setStockBodega] = useState("0");
  const [stockCafeteria, setStockCafeteria] = useState("0");
  const [stockMinimo, setStockMinimo] = useState("0");
  const [costoUnitario, setCostoUnitario] = useState("0");
  const [precioTotal, setPrecioTotal] = useState("");
  const [cantidadCompra, setCantidadCompra] = useState("");
  const costoCalculado = calcularCostoDesdeCompra(precioTotal, cantidadCompra);
  const totalConMargen =
    precioTotal && Number(precioTotal) > 0
      ? Number(precioTotal) * (1 + MARGEN_INSUMO)
      : null;

  const resetForm = () => {
    setNombre("");
    setUnidad("g");
    setUnidadOtra("");
    setStockBodega("0");
    setStockCafeteria("0");
    setStockMinimo("0");
    setCostoUnitario("0");
    setPrecioTotal("");
    setCantidadCompra("");
    setEditing(null);
  };

  const openNewModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = (insumo) => {
    setEditing(insumo);
    setNombre(insumo.nombre);
    const u = insumo.unidad || "g";
    if (UNIDAD_VALUES.includes(u)) {
      setUnidad(u);
      setUnidadOtra("");
    } else {
      setUnidad(UNIDAD_OTRA);
      setUnidadOtra(u);
    }
    setStockBodega(String(insumo.stock_bodega ?? 0));
    setStockCafeteria(String(insumo.stock_cafeteria ?? 0));
    setStockMinimo(String(insumo.stock_minimo ?? 0));
    setCostoUnitario(String(insumo.costo_unitario ?? 0));
    setShowModal(true);
  };

  const openTraspasoModal = (insumo) => {
    setTraspasoInsumo(insumo);
    setTraspasoCantidad("");
    setShowTraspaso(true);
  };

  const loadInsumos = async () => {
    try {
      setLoading(true);
      const data = await getInsumos();
      setInsumos(data);
    } catch (err) {
      console.error("Error al cargar insumos:", err);
      alert("Error al cargar insumos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInsumos();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!nombre.trim()) {
      alert("El nombre es obligatorio");
      return;
    }

    const bodega = parseFloat(stockBodega);
    const cafeteria = parseFloat(stockCafeteria);
    const minimo = parseFloat(stockMinimo);

    let costo;
    if (precioTotal.trim() !== "" || cantidadCompra.trim() !== "") {
      if (!precioTotal || Number(precioTotal) <= 0) {
        alert("Ingresa el precio total pagado (mayor a 0)");
        return;
      }
      if (!cantidadCompra || Number(cantidadCompra) <= 0) {
        alert("Ingresa la cantidad comprada (mayor a 0)");
        return;
      }
      costo = calcularCostoDesdeCompra(precioTotal, cantidadCompra);
    } else {
      costo = parseFloat(costoUnitario);
      if (isNaN(costo) || costo < 0) {
        alert("Ingresa precio total y cantidad, o un costo unitario válido");
        return;
      }
    }

    if (isNaN(bodega) || bodega < 0) {
      alert("El stock en bodega debe ser mayor o igual a 0");
      return;
    }
    if (isNaN(cafeteria) || cafeteria < 0) {
      alert("El stock en cafetería debe ser mayor o igual a 0");
      return;
    }
    if (isNaN(minimo) || minimo < 0) {
      alert("El stock mínimo debe ser mayor o igual a 0");
      return;
    }

    const unidadFinal =
      unidad === UNIDAD_OTRA ? unidadOtra.trim() : unidad.trim();

    if (!unidadFinal) {
      alert("Selecciona o escribe una unidad");
      return;
    }

    const payload = {
      nombre: nombre.trim(),
      unidad: unidadFinal,
      stock_bodega: bodega,
      stock_cafeteria: cafeteria,
      stock_minimo: minimo,
      costo_unitario: costo,
    };

    try {
      if (editing) {
        const costoCambio =
          parseFloat(costoUnitario) !== Number(editing.costo_unitario ?? 0);
        const updated = await updateInsumo(editing.id_insumo, payload);
        const n = updated.productos_precio_actualizados ?? 0;
        if (costoCambio && n > 0) {
          alert(
            `Insumo actualizado. Se recalcularon los precios de ${n} producto(s) con receta activa.`
          );
        } else if (costoCambio) {
          alert(
            "Insumo actualizado. El costo cambió pero no hay productos con receta activa que recalcular."
          );
        } else {
          alert("Insumo actualizado");
        }
      } else {
        await createInsumo(payload);
        alert("Insumo creado");
      }
      setShowModal(false);
      resetForm();
      await loadInsumos();
    } catch (err) {
      console.error("Error:", err);
      const detail = err.response?.data?.detail;
      alert(
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg).join(", ")
            : "Error al guardar el insumo"
      );
    }
  };

  const handleTraspaso = async (e) => {
    e.preventDefault();
    const cantidad = parseFloat(traspasoCantidad);
    if (!traspasoInsumo || isNaN(cantidad) || cantidad <= 0) {
      alert("Ingresa una cantidad válida");
      return;
    }
    try {
      await traspasarInsumo(traspasoInsumo.id_insumo, cantidad);
      alert(`Se surtieron ${cantidad} ${traspasoInsumo.unidad} a cafetería`);
      setShowTraspaso(false);
      setTraspasoInsumo(null);
      setTraspasoCantidad("");
      await loadInsumos();
    } catch (err) {
      const detail = err.response?.data?.detail;
      alert(typeof detail === "string" ? detail : "No se pudo hacer el traspaso");
    }
  };

  const handleDelete = async (insumo) => {
    if (!window.confirm(`¿Eliminar insumo "${insumo.nombre}"?`)) return;

    try {
      await deleteInsumo(insumo.id_insumo);
      alert("Insumo eliminado");
      await loadInsumos();
    } catch (err) {
      console.error("Error:", err);
      alert(
        err.response?.data?.detail ||
          "No se pudo eliminar. Puede estar en uso en una receta."
      );
    }
  };

  const cafeteriaBaja = (insumo) =>
    Number(insumo.stock_cafeteria ?? 0) <= Number(insumo.stock_minimo ?? 0);

  return (
    <div className="page">
      <PageHeader
        title="Insumos"
        subtitle="Control de inventario en bodega y cafetería"
      >
        <button type="button" className="btn btn--primary" onClick={openNewModal}>
          Nuevo insumo
        </button>
      </PageHeader>

      <p className="hint" style={{ marginTop: 0, marginBottom: "1rem" }}>
        Las <strong>compras</strong> suman a bodega. Las <strong>ventas</strong> restan de
        cafetería. Usa <strong>Surtir</strong> para mover de bodega a barra/cocina.
      </p>

      {loading ? (
        <div className="loading-state">Cargando…</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Unidad</th>
                <th>Bodega</th>
                <th>Cafetería</th>
                <th>Total</th>
                <th>Mín. cafetería</th>
                <th>Costo u.</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {insumos.length === 0 ? (
                <tr>
                  <td colSpan="9" className="empty-state">
                    No hay insumos registrados
                  </td>
                </tr>
              ) : (
                insumos.map((i) => (
                  <tr key={i.id_insumo}>
                    <td>{i.nombre}</td>
                    <td>{i.unidad}</td>
                    <td>{Number(i.stock_bodega ?? 0)}</td>
                    <td>{Number(i.stock_cafeteria ?? 0)}</td>
                    <td><strong>{stockTotal(i)}</strong></td>
                    <td>{Number(i.stock_minimo ?? 0)}</td>
                    <td>${Number(i.costo_unitario ?? 0).toFixed(4)}</td>
                    <td>
                      {cafeteriaBaja(i) ? (
                        <span
                          className="badge"
                          style={{ background: "#fde8e8", color: "var(--danger)" }}
                        >
                          Cafetería baja
                        </span>
                      ) : (
                        <span className="badge badge--ok">OK</span>
                      )}
                    </td>
                    <td>
                      <div className="btn-group">
                        <button
                          type="button"
                          className="btn btn--accent btn--sm"
                          onClick={() => openTraspasoModal(i)}
                          disabled={Number(i.stock_bodega ?? 0) <= 0}
                          title="Mover de bodega a cafetería"
                        >
                          Surtir
                        </button>
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm"
                          onClick={() => openEditModal(i)}
                        >
                          Editar
                        </button>
                        <button
                          type="button"
                          className="btn btn--danger btn--sm"
                          onClick={() => handleDelete(i)}
                        >
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h2>{editing ? "Editar insumo" : "Nuevo insumo"}</h2>
            <p className="hint" style={{ marginTop: 0 }}>
              Registra cuánto tienes hoy en bodega y cuánto en cafetería (conteo inicial).
            </p>

            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <label>Nombre *</label>
                <input
                  type="text"
                  className="input"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div className="form-row">
                <label>Unidad *</label>
                <select
                  className="select"
                  value={UNIDAD_VALUES.includes(unidad) ? unidad : UNIDAD_OTRA}
                  onChange={(e) => {
                    const v = e.target.value;
                    setUnidad(v);
                    if (v !== UNIDAD_OTRA) setUnidadOtra("");
                  }}
                  required
                >
                  {UNIDADES.map((u) => (
                    <option key={u.value} value={u.value}>
                      {u.label}
                    </option>
                  ))}
                  <option value={UNIDAD_OTRA}>Otra (escribir)</option>
                </select>
                {(unidad === UNIDAD_OTRA || !UNIDAD_VALUES.includes(unidad)) && (
                  <input
                    type="text"
                    className="input"
                    style={{ marginTop: 8 }}
                    value={unidadOtra}
                    onChange={(e) => setUnidadOtra(e.target.value)}
                    placeholder="Ej. bolsa, caja, sobre..."
                    required
                  />
                )}
              </div>

              <div className="form-grid">
                <div className="form-row">
                  <label>Stock en bodega</label>
                  <input
                    type="number"
                    className="input"
                    min="0"
                    step="0.001"
                    value={stockBodega}
                    onChange={(e) => setStockBodega(e.target.value)}
                  />
                </div>
                <div className="form-row">
                  <label>Stock en cafetería</label>
                  <input
                    type="number"
                    className="input"
                    min="0"
                    step="0.001"
                    value={stockCafeteria}
                    onChange={(e) => setStockCafeteria(e.target.value)}
                  />
                </div>
                <div className="form-row">
                  <label>Mínimo en cafetería</label>
                  <input
                    type="number"
                    className="input"
                    min="0"
                    step="0.001"
                    value={stockMinimo}
                    onChange={(e) => setStockMinimo(e.target.value)}
                  />
                  <p className="hint" style={{ margin: "0.35rem 0 0" }}>
                    Alerta cuando cafetería esté en o bajo este nivel.
                  </p>
                </div>
              </div>

              <div className="section" style={{ marginTop: "1rem" }}>
                <label style={{ fontWeight: 600 }}>Calcular costo unitario desde compra</label>
                <p className="hint" style={{ margin: "0.35rem 0 0.75rem" }}>
                  Precio total + 10% ÷ cantidad
                </p>
                <div className="form-grid">
                  <div className="form-row">
                    <label>Precio total pagado ($)</label>
                    <input
                      type="number"
                      className="input"
                      min="0"
                      step="0.01"
                      value={precioTotal}
                      onChange={(e) => setPrecioTotal(e.target.value)}
                      placeholder="Ej. 500"
                    />
                  </div>
                  <div className="form-row">
                    <label>Cantidad comprada</label>
                    <input
                      type="number"
                      className="input"
                      min="0"
                      step="0.001"
                      value={cantidadCompra}
                      onChange={(e) => setCantidadCompra(e.target.value)}
                      placeholder="Ej. 1000"
                    />
                  </div>
                </div>
                {totalConMargen != null && costoCalculado != null && (
                  <p className="hint" style={{ marginBottom: 0 }}>
                    Costo unitario calculado: <strong>${costoCalculado.toFixed(4)}</strong>
                  </p>
                )}
              </div>

              <div className="form-row">
                <label>Costo unitario (manual)</label>
                <input
                  type="number"
                  className="input"
                  min="0"
                  step="0.0001"
                  value={costoUnitario}
                  onChange={(e) => setCostoUnitario(e.target.value)}
                  disabled={precioTotal !== "" || cantidadCompra !== ""}
                />
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    resetForm();
                  }}
                  className="btn btn--secondary"
                >
                  Cancelar
                </button>
                <button type="submit" className="btn btn--primary">
                  {editing ? "Actualizar" : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showTraspaso && traspasoInsumo && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h2>Surtir a cafetería</h2>
            <p className="hint">
              <strong>{traspasoInsumo.nombre}</strong> — en bodega:{" "}
              {Number(traspasoInsumo.stock_bodega ?? 0)} {traspasoInsumo.unidad}
            </p>
            <form onSubmit={handleTraspaso}>
              <div className="form-row">
                <label>Cantidad a mover a cafetería</label>
                <input
                  type="number"
                  className="input"
                  min="0.001"
                  step="0.001"
                  max={Number(traspasoInsumo.stock_bodega ?? 0)}
                  value={traspasoCantidad}
                  onChange={(e) => setTraspasoCantidad(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => {
                    setShowTraspaso(false);
                    setTraspasoInsumo(null);
                  }}
                >
                  Cancelar
                </button>
                <button type="submit" className="btn btn--accent">
                  Confirmar traspaso
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
