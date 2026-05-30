import { useEffect, useState } from "react";
import {
  getCategorias,
  createCategoria,
  updateCategoria,
  deleteCategoria,
} from "../services/categoriasService";
import PageHeader from "../components/PageHeader";

export default function Categorias() {
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [nombre, setNombre] = useState("");

  const resetForm = () => {
    setNombre("");
    setEditing(null);
  };

  const openNewModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = (categoria) => {
    setEditing(categoria);
    setNombre(categoria.nombre);
    setShowModal(true);
  };

  const loadCategorias = async () => {
    try {
      setLoading(true);
      const data = await getCategorias();
      setCategorias(data);
    } catch (err) {
      console.error("Error al cargar categorías:", err);
      alert("Error al cargar categorías");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCategorias();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!nombre.trim()) {
      alert("El nombre es obligatorio");
      return;
    }
    const payload = { nombre: nombre.trim() };
    try {
      if (editing) {
        await updateCategoria(editing.id_categoria, payload);
        alert("Categoría actualizada");
      } else {
        await createCategoria(payload);
        alert("Categoría creada");
      }
      setShowModal(false);
      resetForm();
      await loadCategorias();
    } catch (err) {
      console.error("Error:", err);
      alert(err.response?.data?.detail || "Error al guardar la categoría");
    }
  };

  const handleDelete = async (categoria) => {
    if (!window.confirm(`¿Eliminar "${categoria.nombre}"?`)) return;
    try {
      await deleteCategoria(categoria.id_categoria);
      await loadCategorias();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar");
    }
  };

  return (
    <div className="page">
      <PageHeader title="Categorías" subtitle="Tipos de productos del menú">
        <button type="button" className="btn btn--primary" onClick={openNewModal}>
          Nueva categoría
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
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {categorias.length === 0 ? (
                <tr>
                  <td colSpan="3" className="empty-state">
                    No hay categorías
                  </td>
                </tr>
              ) : (
                categorias.map((c) => (
                  <tr key={c.id_categoria}>
                    <td>{c.id_categoria}</td>
                    <td>{c.nombre}</td>
                    <td>
                      <div className="btn-group">
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm"
                          onClick={() => openEditModal(c)}
                        >
                          Editar
                        </button>
                        <button
                          type="button"
                          className="btn btn--danger btn--sm"
                          onClick={() => handleDelete(c)}
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
            <h2>{editing ? "Editar categoría" : "Nueva categoría"}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <label>Nombre *</label>
                <input
                  type="text"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => setShowModal(false)}
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
