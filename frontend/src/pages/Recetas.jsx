import { useEffect, useState, useMemo } from "react";
import {
  getRecetas,
  getReceta,
  createReceta,
  updateReceta,
  deleteReceta,
} from "../services/recetasService";
import { getInsumos } from "../services/insumosService";
import { getProductos } from "../services/productosService";
import PageHeader from "../components/PageHeader";

export default function Recetas() {
  const [recetas, setRecetas] = useState([]);
  const [loading, setLoading] = useState(false);

  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);

  const [productos, setProductos] = useState([]);
  const [insumos, setInsumos] = useState([]);

  // FORM
  const [idProducto, setIdProducto] = useState("");
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [activo, setActivo] = useState(true);
  const [listaInsumos, setListaInsumos] = useState([]);
  const [busquedaInsumo, setBusquedaInsumo] = useState("");

  const insumosFiltrados = useMemo(() => {
    const q = busquedaInsumo.trim().toLowerCase();
    const idsYaAgregados = new Set(
      listaInsumos.map((i) => Number(i.id_insumo)).filter(Boolean)
    );
    return insumos.filter((i) => {
      if (idsYaAgregados.has(i.id_insumo)) return false;
      if (!q) return true;
      return i.nombre.toLowerCase().includes(q);
    });
  }, [insumos, busquedaInsumo, listaInsumos]);

  // ============================
  // RESET FORM
  // ============================
  const resetForm = () => {
    setIdProducto("");
    setNombre("");
    setDescripcion("");
    setActivo(true);
    setListaInsumos([]);
    setBusquedaInsumo("");
    setEditing(null);
  };

  // ============================
  // LOAD RECETAS
  // ============================
  const loadRecetas = async () => {
    try {
      setLoading(true);
      const data = await getRecetas();
      setRecetas(data);
    } catch (err) {
      console.error(err);
      alert("Error al cargar recetas");
    } finally {
      setLoading(false);
    }
  };

  // ============================
  // LOAD PRODUCTOS + INSUMOS
  // ============================
  const loadCatalogos = async () => {
    try {
      const [prods, ins] = await Promise.all([getProductos(), getInsumos()]);
      setProductos(prods);
      setInsumos(
        [...ins].sort((a, b) =>
          a.nombre.localeCompare(b.nombre, "es", { sensitivity: "base" })
        )
      );
    } catch (err) {
      console.error(err);
      alert("Error al cargar productos/insumos");
    }
  };

  useEffect(() => {
    loadRecetas();
    loadCatalogos();
  }, []);

  // ============================
  // MODALES
  // ============================
  const openNewModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = async (receta) => {
    try {
      resetForm();
      setEditing(receta);

      const data = await getReceta(receta.id_receta);

      setIdProducto(data.id_producto);
      setNombre(data.nombre);
      setDescripcion(data.descripcion || "");
      setActivo(data.activo);

      setListaInsumos(
        (data.insumos || []).map((i) => ({
          id_insumo: Number(i.id_insumo),
          cantidad: Number(i.cantidad),
        }))
      );

      setShowModal(true);
    } catch (err) {
      console.error(err);
      alert("Error al cargar la receta");
    }
  };

  // ============================
  // INSUMOS EN FORMULARIO
  // ============================
  const agregarInsumoDesdeBusqueda = (idInsumo) => {
    const id = Number(idInsumo);
    if (!id) return;

    if (listaInsumos.some((i) => Number(i.id_insumo) === id)) {
      alert("Ese insumo ya está en la lista");
      setBusquedaInsumo("");
      return;
    }

    setListaInsumos([...listaInsumos, { id_insumo: id, cantidad: 1 }]);
    setBusquedaInsumo("");
  };

  const updateInsumo = (index, field, value) => {
    const updated = [...listaInsumos];
    updated[index][field] = value;
    setListaInsumos(updated);
  };

  const removeInsumo = (index) => {
    const updated = listaInsumos.filter((_, i) => i !== index);
    setListaInsumos(updated);
  };

  const calcularCostoTotal = () => {
    return listaInsumos.reduce((acc, item) => {
      const ins = insumos.find(
        (i) => i.id_insumo === Number(item.id_insumo)
      );
      if (!ins) return acc;
      const costoUnit = Number(ins.costo_unitario) || 0;
      const cant = Number(item.cantidad) || 0;
      return acc + costoUnit * cant;
    }, 0);
  };

  // ============================
  // SUBMIT
  // ============================
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!idProducto) {
      alert("Selecciona un producto");
      return;
    }

    if (!nombre.trim()) {
      alert("El nombre es obligatorio");
      return;
    }

    if (listaInsumos.length === 0) {
      alert("Agrega al menos un insumo");
      return;
    }

    // Validar que todos los insumos seleccionados existan y tengan cantidad
    for (let i = 0; i < listaInsumos.length; i++) {
      const item = listaInsumos[i];
      
      if (!item.id_insumo) {
        alert(`Insumo ${i + 1}: Selecciona un insumo`);
        return;
      }

      if (!item.cantidad || Number(item.cantidad) <= 0) {
        alert(`Insumo ${i + 1}: La cantidad debe ser mayor a 0`);
        return;
      }

      // Validar que el insumo exista en la lista disponible
      const insumoExiste = insumos.find(
        (ins) => ins.id_insumo === Number(item.id_insumo)
      );
      if (!insumoExiste) {
        alert(
          `Insumo ${i + 1}: El insumo seleccionado no existe o fue eliminado`
        );
        return;
      }
    }

    const payload = {
      id_producto: Number(idProducto),
      nombre,
      descripcion,
      activo,
      insumos: listaInsumos.map((i) => ({
        id_insumo: Number(i.id_insumo),
        cantidad: Number(i.cantidad),
      })),
    };

    try {
      if (editing) {
        await updateReceta(editing.id_receta, payload);
      } else {
        await createReceta(payload);
      }

      setShowModal(false);
      resetForm();
      await loadRecetas();
    } catch (err) {
      console.error("❌ Error completo:", err);
      alert(
        "Error al guardar la receta: " +
          (err.response?.data?.detail || err.message)
      );
    }
  };

  // ============================
  // DELETE
  // ============================
  const handleDelete = async (receta) => {
    if (!window.confirm(`¿Eliminar receta "${receta.nombre}"?`)) return;

    try {
      await deleteReceta(receta.id_receta);
      await loadRecetas();
    } catch (err) {
      console.error(err);
      alert("Error al eliminar receta");
    }
  };

  // ============================
  // RENDER
  // ============================
  return (
    <div className="page">
      <PageHeader title="Recetas" subtitle="Composición y costo de cada producto">
        <button type="button" className="btn btn--primary" onClick={openNewModal}>
          Nueva receta
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
                <th>Producto</th>
                <th>Nombre</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {recetas.length === 0 ? (
                <tr>
                  <td colSpan="5" className="empty-state">
                    No hay recetas
                  </td>
                </tr>
              ) : (
                recetas.map((r) => (
                  <tr key={r.id_receta}>
                    <td>{r.id_receta}</td>
                    <td>{r.producto_nombre || r.id_producto}</td>
                    <td>{r.nombre}</td>
                    <td>
                      <span className={r.activo ? "badge badge--ok" : "badge badge--off"}>
                        {r.activo ? "Activa" : "Inactiva"}
                      </span>
                    </td>
                    <td>
                      <div className="btn-group">
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm"
                          onClick={() => openEditModal(r)}
                        >
                          Editar
                        </button>
                        <button
                          type="button"
                          className="btn btn--danger btn--sm"
                          onClick={() => handleDelete(r)}
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
            <h2>{editing ? "Editar receta" : "Nueva receta"}</h2>

            <form onSubmit={handleSubmit}>
              {/* PRODUCTO */}
              <div style={formGroup}>
                <label>Producto</label>
                <select
                  value={idProducto}
                  onChange={(e) => setIdProducto(e.target.value)}
                  style={inputStyle}
                >
                  <option value="">Seleccione...</option>
                  {productos.map((p) => (
                    <option key={p.id_producto} value={p.id_producto}>
                      {p.nombre}
                    </option>
                  ))}
                </select>
              </div>

              {/* NOMBRE */}
              <div style={formGroup}>
                <label>Nombre de la receta</label>
                <input
                  type="text"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  style={inputStyle}
                />
              </div>

              {/* DESCRIPCION */}
              <div style={formGroup}>
                <label>Descripción</label>
                <textarea
                  value={descripcion}
                  onChange={(e) => setDescripcion(e.target.value)}
                  style={{ ...inputStyle, minHeight: 80 }}
                />
              </div>

              {/* INSUMOS */}
              <h3>Insumos</h3>
              <div style={formGroup}>
                <input
                  type="text"
                  placeholder="Buscar e agregar insumo por nombre..."
                  value={busquedaInsumo}
                  onChange={(e) => setBusquedaInsumo(e.target.value)}
                  style={inputStyle}
                />
                {busquedaInsumo.trim() !== "" && (
                  <div style={sugerenciasBox}>
                    {insumosFiltrados.length === 0 ? (
                      <div style={sugerenciaItemVacio}>No hay insumos que coincidan</div>
                    ) : (
                      insumosFiltrados.slice(0, 8).map((i) => (
                        <button
                          key={i.id_insumo}
                          type="button"
                          style={sugerenciaItem}
                          onClick={() => agregarInsumoDesdeBusqueda(i.id_insumo)}
                        >
                          {i.nombre} ({i.unidad}) — $
                          {Number(i.costo_unitario ?? 0).toFixed(4)}
                        </button>
                      ))
                    )}
                  </div>
                )}
                <small style={{ color: "#6b7280" }}>
                  Escribe el nombre y haz clic en el resultado para agregarlo.
                </small>
              </div>

              {listaInsumos.length === 0 ? (
                <p style={{ color: "#6b7280", marginBottom: 12 }}>
                  Aún no hay insumos en la receta.
                </p>
              ) : (
                listaInsumos.map((item, index) => {
                  const ins = insumos.find(
                    (i) => i.id_insumo === Number(item.id_insumo)
                  );
                  const costoUnit = ins ? Number(ins.costo_unitario) : 0;
                  const cant = Number(item.cantidad) || 0;
                  const subtotal = costoUnit * cant;

                  return (
                    <div key={item.id_insumo || index} style={insumoRow}>
                      <div style={{ flex: 1, minWidth: 140, paddingTop: 6 }}>
                        <strong>{ins?.nombre || `Insumo #${item.id_insumo}`}</strong>
                        {ins?.unidad ? (
                          <small style={{ marginLeft: 6, color: "#6b7280" }}>
                            ({ins.unidad})
                          </small>
                        ) : null}
                      </div>

                      <input
                        type="number"
                        min="0"
                        step="0.001"
                        value={item.cantidad}
                        onChange={(e) =>
                          updateInsumo(index, "cantidad", Number(e.target.value))
                        }
                        style={{ ...inputStyle, width: 120 }}
                        placeholder="Cantidad"
                      />

                      <div style={{ minWidth: 120 }}>
                        <small>Costo unitario: ${costoUnit.toFixed(4)}</small>
                        <br />
                        <small>Subtotal: ${subtotal.toFixed(2)}</small>
                      </div>

                      <button type="button" onClick={() => removeInsumo(index)}>
                        X
                      </button>
                    </div>
                  );
                })
              )}

              {/* COSTO TOTAL */}
              <div style={{ marginTop: 20, fontWeight: "bold" }}>
                Costo total: ${calcularCostoTotal().toFixed(2)}
              </div>

              {/* ACTIVO */}
              <div style={formGroup}>
                <label>
                  <input
                    type="checkbox"
                    checked={activo}
                    onChange={(e) => setActivo(e.target.checked)}
                    style={{ marginRight: 6 }}
                  />
                  Activa
                </label>
              </div>

              {/* BOTONES */}
              <div style={footerButtons}>
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    resetForm();
                  }}
                  style={{ marginRight: 8 }}
                >
                  Cancelar
                </button>
                <button type="submit">
                  {editing ? "Guardar cambios" : "Crear receta"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


/* ESTILOS */
const formGroup = { marginBottom: 10 };

const inputStyle = {
  width: "100%",
  padding: 6,
  boxSizing: "border-box",
};

const insumoRow = {
  display: "flex",
  gap: 10,
  marginBottom: 10,
  alignItems: "flex-start",
  flexWrap: "wrap",
};

const sugerenciasBox = {
  border: "1px solid #e5e7eb",
  borderRadius: 6,
  marginTop: 6,
  maxHeight: 220,
  overflowY: "auto",
  background: "#fff",
};

const sugerenciaItem = {
  display: "block",
  width: "100%",
  textAlign: "left",
  border: "none",
  borderBottom: "1px solid #f3f4f6",
  background: "#fff",
  padding: "8px 10px",
  cursor: "pointer",
};

const sugerenciaItemVacio = {
  padding: "8px 10px",
  color: "#6b7280",
};

const footerButtons = {
  display: "flex",
  justifyContent: "flex-end",
  marginTop: 20,
};
