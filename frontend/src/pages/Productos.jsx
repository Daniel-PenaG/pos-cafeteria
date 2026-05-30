import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getProductos,
  createProducto,
  updateProducto,
  deleteProducto,
  getCategorias,
} from "../services/productosService";
import { createCategoria } from "../services/categoriasService";
import PageHeader from "../components/PageHeader";

export default function Productos() {
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const [showModal, setShowModal] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [editing, setEditing] = useState(null);

  const [nombre, setNombre] = useState("");
  const [idCategoria, setIdCategoria] = useState("");
  const [precioVenta, setPrecioVenta] = useState("");
  const [activo, setActivo] = useState(true);

  const [nombreCategoria, setNombreCategoria] = useState("");

  const resetForm = () => {
    setNombre("");
    setIdCategoria("");
    setPrecioVenta("");
    setActivo(true);
    setEditing(null);
  };

  const openNewModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = (producto) => {
    setEditing(producto);
    setNombre(producto.nombre);
    setIdCategoria(producto.id_categoria);
    setPrecioVenta(producto.precio_venta);
    setActivo(producto.activo);
    setShowModal(true);
  };

  const loadCategorias = async () => {
    try {
      const data = await getCategorias();
      setCategorias(data);
    } catch (err) {
      console.error("Error al cargar categorías:", err);
    }
  };

  const loadProductos = async () => {
    try {
      setLoading(true);
      const data = await getProductos();
      setProductos(data);
    } catch (err) {
      console.error("Error al cargar productos:", err);
      alert("Error al cargar productos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCategorias();
    loadProductos();
  }, []);

  const handleCreateCategory = async (e) => {
    e.preventDefault();

    if (!nombreCategoria.trim()) {
      alert("El nombre de la categoría es obligatorio");
      return;
    }

    try {
      const newCategory = await createCategoria({ nombre: nombreCategoria.trim() });
      setCategorias([...categorias, newCategory]);
      setIdCategoria(newCategory.id_categoria);
      setNombreCategoria("");
      setShowCategoryModal(false);
      alert("Categoría creada exitosamente");
    } catch (err) {
      console.error("Error:", err);
      alert(err.response?.data?.detail || "Error al crear la categoría");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!nombre.trim()) {
      alert("El nombre es obligatorio");
      return;
    }

    if (!idCategoria) {
      alert("Selecciona una categoría");
      return;
    }

    if (!precioVenta || parseFloat(precioVenta) <= 0) {
      alert("El precio debe ser mayor a 0");
      return;
    }

    const payload = {
      nombre: nombre.trim(),
      id_categoria: parseInt(idCategoria),
      precio_venta: parseFloat(precioVenta),
      activo,
    };

    try {
      if (editing) {
        await updateProducto(editing.id_producto, payload);
        alert("Producto actualizado");
      } else {
        await createProducto(payload);
        alert("Producto creado");
      }
      setShowModal(false);
      resetForm();
      await loadProductos();
    } catch (err) {
      console.error("Error:", err);
      alert(err.response?.data?.detail || "Error al guardar el producto");
    }
  };

  const handleDelete = async (producto) => {
    if (!window.confirm(`¿Eliminar producto "${producto.nombre}"?`)) return;

    try {
      await deleteProducto(producto.id_producto);
      alert("Producto eliminado");
      await loadProductos();
    } catch (err) {
      console.error("Error:", err);
      alert("Error al eliminar el producto");
    }
  };

  const getCategoryName = (id) => {
    const cat = categorias.find((c) => c.id_categoria === id);
    return cat ? cat.nombre : "N/A";
  };

  return (
    <div className="page">
      <PageHeader title="Productos" subtitle="Menú y precios de venta">
        <button type="button" className="btn btn--primary" onClick={openNewModal}>
          Nuevo producto
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
                <th>Categoría</th>
                <th>Precio</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {productos.length === 0 ? (
                <tr>
                  <td colSpan="6" className="empty-state">
                    No hay productos
                  </td>
                </tr>
              ) : (
                productos.map((p) => (
                  <tr key={p.id_producto}>
                    <td>{p.id_producto}</td>
                    <td>{p.nombre}</td>
                    <td>{getCategoryName(p.id_categoria)}</td>
                    <td>${parseFloat(p.precio_venta).toFixed(2)}</td>
                    <td>
                      <span className={p.activo ? "badge badge--ok" : "badge badge--off"}>
                        {p.activo ? "Activo" : "Inactivo"}
                      </span>
                    </td>
                    <td>
                      <div className="btn-group">
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm"
                          onClick={() => openEditModal(p)}
                        >
                          Editar
                        </button>
                        <button
                          type="button"
                          className="btn btn--accent btn--sm"
                          onClick={() => {
                            alert(
                              `Para actualizar el precio de "${p.nombre}", crea o edita su receta en Recetas.`
                            );
                            navigate("/recetas");
                          }}
                        >
                          Receta
                        </button>
                        <button
                          type="button"
                          className="btn btn--danger btn--sm"
                          onClick={() => handleDelete(p)}
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
            <h2>{editing ? "Editar producto" : "Nuevo producto"}</h2>

            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <label>Nombre *</label>
                <input
                  type="text"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  required
                />
              </div>

              <div className="form-row">
                <div className="table-toolbar" style={{ marginBottom: "0.35rem" }}>
                  <label style={{ margin: 0 }}>Categoría *</label>
                  <button
                    type="button"
                    className="btn btn--accent btn--sm"
                    onClick={() => setShowCategoryModal(true)}
                  >
                    + Nueva
                  </button>
                </div>
                <select
                  className="select"
                  value={idCategoria}
                  onChange={(e) => setIdCategoria(e.target.value)}
                  required
                >
                  <option value="">Seleccionar categoría</option>
                  {categorias.map((cat) => (
                    <option key={cat.id_categoria} value={cat.id_categoria}>
                      {cat.nombre}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-row">
                <label>Precio de venta ($) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={precioVenta}
                  onChange={(e) => setPrecioVenta(e.target.value)}
                  required
                />
                <p className="hint" style={{ marginTop: "0.35rem" }}>
                  Con receta activa, el precio se recalcula automáticamente.
                </p>
              </div>

              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
                <input
                  type="checkbox"
                  checked={activo}
                  onChange={(e) => setActivo(e.target.checked)}
                />
                Activo
              </label>

              <div className="modal-footer">
                <button type="button" className="btn btn--secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn--primary">
                  {editing ? "Actualizar" : "Crear"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showCategoryModal && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h2>Nueva categoría</h2>
            <form onSubmit={handleCreateCategory}>
              <div className="form-row">
                <label>Nombre *</label>
                <input
                  type="text"
                  value={nombreCategoria}
                  onChange={(e) => setNombreCategoria(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => {
                    setShowCategoryModal(false);
                    setNombreCategoria("");
                  }}
                >
                  Cancelar
                </button>
                <button type="submit" className="btn btn--accent">
                  Crear
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
