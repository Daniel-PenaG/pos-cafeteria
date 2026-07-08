import { useEffect, useState } from "react";
import {
  getInsumos,
  createInsumo,
  updateInsumo,
  deleteInsumo,
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

/** costo_unitario = (precio_total * 1.10) / cantidad */
function calcularCostoDesdeCompra(precioTotal, cantidad) {
  const total = Number(precioTotal);
  const cant = Number(cantidad);
  if (!total || total <= 0 || !cant || cant <= 0) return null;
  const totalConMargen = total * (1 + MARGEN_INSUMO);
  return totalConMargen / cant;
}

export default function Insumos() {
  const [insumos, setInsumos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);

  const [nombre, setNombre] = useState("");
  const [unidad, setUnidad] = useState("g");
  const [unidadOtra, setUnidadOtra] = useState("");
  const [stockActual, setStockActual] = useState("0");
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
    setStockActual("0");
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
    setStockActual(String(insumo.stock_actual ?? 0));
    setStockMinimo(String(insumo.stock_minimo ?? 0));
    setCostoUnitario(String(insumo.costo_unitario ?? 0));
    setShowModal(true);
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

    const stock = parseFloat(stockActual);
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

    if (isNaN(stock) || stock < 0) {
      alert("El stock actual debe ser un número mayor o igual a 0");
      return;
    }
    if (isNaN(minimo) || minimo < 0) {
      alert("El stock mínimo debe ser un número mayor o igual a 0");
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
      stock_actual: stock,
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

  const stockBajo = (insumo) =>
    Number(insumo.stock_actual) <= Number(insumo.stock_minimo);

  return (
    <div className="page">
      <PageHeader
        title="Insumos"
        subtitle="Materia prima para recetas y reabastecimiento"
      >
        <button type="button" className="btn btn--primary" onClick={openNewModal}>
          Nuevo insumo
        </button>
      </PageHeader>

      {loading ? (
        <div className="loading-state">Cargando…</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
                <th>Unidad</th>
                <th>Stock actual</th>
                <th>Stock mínimo</th>
                <th>Costo unitario</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
          <tbody>
            {insumos.length === 0 ? (
              <tr>
                <td colSpan="8" className="empty-state">
                  No hay insumos registrados
                </td>
              </tr>
            ) : (
              insumos.map((i) => (
                <tr key={i.id_insumo}>
                  <td>{i.id_insumo}</td>
                  <td>{i.nombre}</td>
                  <td>{i.unidad}</td>
                  <td>{Number(i.stock_actual)}</td>
                  <td>{Number(i.stock_minimo)}</td>
                  <td>${Number(i.costo_unitario ?? 0).toFixed(4)}</td>
                  <td>
                    {stockBajo(i) ? (
                      <span className="badge" style={{ background: "#fde8e8", color: "var(--danger)" }}>
                        Stock bajo
                      </span>
                    ) : (
                      <span className="badge badge--ok">OK</span>
                    )}
                  </td>
                  <td>
                    <div className="btn-group">
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

            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", marginBottom: 6 }}>
                  Nombre *
                </label>
                <input
                  type="text"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", marginBottom: 6 }}>
                  Unidad *
                </label>
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

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ display: "block", marginBottom: 6 }}>
                    Stock actual
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={stockActual}
                    onChange={(e) => setStockActual(e.target.value)}
                  />
                </div>
                <div>
                  <label style={{ display: "block", marginBottom: 6 }}>
                    Stock mínimo
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={stockMinimo}
                    onChange={(e) => setStockMinimo(e.target.value)}
                  />
                </div>
              </div>

              <div
                style={{
                  marginTop: 16,
                  marginBottom: 16,
                  padding: 12,
                  backgroundColor: "#f0f9ff",
                  borderRadius: 8,
                  border: "1px solid #bae6fd",
                }}
              >
                <label style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>
                  Calcular costo unitario desde compra
                </label>
                <p style={{ margin: "0 0 12px", fontSize: 13, color: "#555" }}>
                  Precio total + 10% ÷ cantidad. Ej: $500 → $550 ÷ 1000 = $0.55 c/u
                </p>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 12,
                    marginBottom: 12,
                  }}
                >
                  <div>
                    <label style={{ display: "block", marginBottom: 6, fontSize: 13 }}>
                      Precio total pagado ($)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={precioTotal}
                      onChange={(e) => setPrecioTotal(e.target.value)}
                      placeholder="Ej. 500"
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", marginBottom: 6, fontSize: 13 }}>
                      Cantidad comprada
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.001"
                      value={cantidadCompra}
                      onChange={(e) => setCantidadCompra(e.target.value)}
                      placeholder="Ej. 1000"
                    />
                  </div>
                </div>
                {totalConMargen != null && costoCalculado != null && (
                  <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6 }}>
                    <div>
                      Total + 10%: <strong>${totalConMargen.toFixed(2)}</strong>
                      <span style={{ color: "#888" }}>
                        {" "}
                        (${Number(precioTotal).toFixed(2)} × 1.10)
                      </span>
                    </div>
                    <div>
                      Costo unitario: <strong>${costoCalculado.toFixed(4)}</strong>
                      <span style={{ color: "#888" }}>
                        {" "}
                        (${totalConMargen.toFixed(2)} ÷ {cantidadCompra})
                      </span>
                    </div>
                  </div>
                )}
              </div>

              <div className="form-row">
                <label>Costo unitario (manual, si no usas el cálculo de arriba)</label>
                <input
                  type="number"
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
    </div>
  );
}
