import { useEffect, useMemo, useState } from "react";
import { getProductos, getCategorias, saveParaLlevarConfig } from "../services/productosService";
import PageHeader from "../components/PageHeader";

export default function ParaLlevar() {
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [seleccionados, setSeleccionados] = useState(new Set());
  const [busqueda, setBusqueda] = useState("");
  const [loading, setLoading] = useState(true);
  const [guardando, setGuardando] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      const [prods, cats] = await Promise.all([getProductos(), getCategorias()]);
      const activos = prods.filter((p) => p.activo !== false);
      setProductos(activos);
      setCategorias(cats);
      const marcados = activos.filter((p) => p.para_llevar);
      setSeleccionados(
        new Set(
          (marcados.length > 0 ? marcados : activos).map((p) => p.id_producto)
        )
      );
    } catch (err) {
      console.error(err);
      alert("Error al cargar productos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const categoriaNombre = (id) =>
    categorias.find((c) => c.id_categoria === id)?.nombre || "Sin categoría";

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return productos
      .filter((p) => !q || p.nombre.toLowerCase().includes(q))
      .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  }, [productos, busqueda]);

  const toggle = (id) => {
    setSeleccionados((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const marcarTodos = () => {
    setSeleccionados(new Set(filtrados.map((p) => p.id_producto)));
  };

  const desmarcarTodos = () => {
    setSeleccionados(new Set());
  };

  const guardar = async () => {
    try {
      setGuardando(true);
      await saveParaLlevarConfig([...seleccionados]);
      alert(`Se guardaron ${seleccionados.size} producto(s) para llevar.`);
      await load();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al guardar");
    } finally {
      setGuardando(false);
    }
  };

  if (loading) return <div className="loading-state">Cargando…</div>;

  return (
    <div className="page">
      <PageHeader
        title="Productos para llevar"
        subtitle="Mismo catálogo que ventas en mesa. Marca cuáles prefieres destacar para llevar (opcional)."
      />

      <section className="card">
        <div className="table-toolbar">
          <p className="hint" style={{ margin: 0 }}>
            {seleccionados.size} producto(s) marcados para llevar
          </p>
          <div className="btn-group">
            <button type="button" className="btn btn--secondary btn--sm" onClick={marcarTodos}>
              Marcar visibles
            </button>
            <button type="button" className="btn btn--secondary btn--sm" onClick={desmarcarTodos}>
              Quitar todos
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={guardar}
              disabled={guardando}
            >
              {guardando ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>

        <input
          type="text"
          className="input"
          placeholder="Buscar producto…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          style={{ marginBottom: "1rem" }}
        />

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: "3rem" }}>Llevar</th>
                <th>Producto</th>
                <th>Categoría</th>
                <th>Precio</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.length === 0 ? (
                <tr>
                  <td colSpan="4" className="empty-state">
                    No hay productos
                  </td>
                </tr>
              ) : (
                filtrados.map((p) => (
                  <tr key={p.id_producto}>
                    <td>
                      <input
                        type="checkbox"
                        checked={seleccionados.has(p.id_producto)}
                        onChange={() => toggle(p.id_producto)}
                      />
                    </td>
                    <td>{p.nombre}</td>
                    <td>{categoriaNombre(p.id_categoria)}</td>
                    <td>${Number(p.precio_venta).toFixed(2)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
