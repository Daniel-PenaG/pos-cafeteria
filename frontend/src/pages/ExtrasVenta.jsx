import { useEffect, useMemo, useState } from "react";
import {
  getExtrasCatalogo,
  getInsumosImportables,
  createExtra,
  createExtraDesdeInsumo,
  updateExtra,
  deleteExtra,
  getProductoExtrasConfig,
  saveProductoExtrasConfig,
} from "../services/extrasVentaService";
import { getProductos } from "../services/productosService";
import PageHeader from "../components/PageHeader";

const TIPOS = [
  { value: "CAFE", label: "Café" },
  { value: "LECHE", label: "Leche" },
  { value: "SABORIZANTE", label: "Saborizante" },
  { value: "OTRO", label: "Otro" },
];

export default function ExtrasVenta() {
  const [extras, setExtras] = useState([]);
  const [insumosImportables, setInsumosImportables] = useState([]);
  const [productos, setProductos] = useState([]);
  const [productoSel, setProductoSel] = useState("");
  const [idsEnlazados, setIdsEnlazados] = useState([]);
  const [loading, setLoading] = useState(false);

  const [showModal, setShowModal] = useState(false);
  const [modoModal, setModoModal] = useState("manual");
  const [editing, setEditing] = useState(null);
  const [nombre, setNombre] = useState("");
  const [unidad, setUnidad] = useState("");
  const [tieneCosto, setTieneCosto] = useState(false);
  const [precioExtra, setPrecioExtra] = useState("");
  const [tipo, setTipo] = useState("OTRO");
  const [activo, setActivo] = useState(true);
  const [insumoSel, setInsumoSel] = useState("");

  const precioPreview = useMemo(() => {
    if (!tieneCosto) return 0;
    const p = parseFloat(precioExtra);
    return isNaN(p) ? 0 : p;
  }, [tieneCosto, precioExtra]);

  const loadExtras = async () => {
    const data = await getExtrasCatalogo();
    setExtras(data);
  };

  const loadProductos = async () => {
    const data = await getProductos();
    setProductos(
      data
        .filter((p) => p.activo !== false)
        .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
    );
  };

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        await Promise.all([loadExtras(), loadProductos()]);
      } catch (err) {
        console.error(err);
        alert("Error al cargar datos");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!productoSel) {
      setIdsEnlazados([]);
      return;
    }
    (async () => {
      try {
        const cfg = await getProductoExtrasConfig(Number(productoSel));
        setIdsEnlazados(cfg.ids_extras || []);
      } catch (err) {
        console.error(err);
        alert("Error al cargar extras del producto");
      }
    })();
  }, [productoSel]);

  const resetForm = () => {
    setNombre("");
    setUnidad("");
    setTieneCosto(false);
    setPrecioExtra("");
    setTipo("OTRO");
    setActivo(true);
    setInsumoSel("");
    setEditing(null);
    setModoModal("manual");
  };

  const openNewManual = () => {
    resetForm();
    setModoModal("manual");
    setShowModal(true);
  };

  const openNewFromInsumo = async () => {
    resetForm();
    setModoModal("insumo");
    try {
      const lista = await getInsumosImportables();
      setInsumosImportables(lista);
      setShowModal(true);
    } catch (err) {
      alert(err.response?.data?.detail || "Error al cargar insumos");
    }
  };

  const openEdit = (e) => {
    setEditing(e);
    setModoModal("edit");
    setNombre(e.nombre);
    setUnidad(e.unidad || "");
    const precio = Number(e.precio) || 0;
    setTieneCosto(precio > 0);
    setPrecioExtra(precio > 0 ? String(precio) : "");
    setTipo(e.tipo || "OTRO");
    setActivo(e.activo !== false);
    setShowModal(true);
  };

  const onInsumoSelect = (id) => {
    setInsumoSel(id);
    const ins = insumosImportables.find((i) => String(i.id_insumo) === String(id));
    if (ins) {
      setNombre(ins.nombre);
      setUnidad(ins.unidad);
      setTieneCosto(false);
      setPrecioExtra("");
    }
  };

  const buildPayloadPrecio = () => {
    if (!tieneCosto) {
      return {
        cantidad: 1,
        costo_unitario: 0,
        usar_precio_manual: true,
        precio_personalizado: 0,
      };
    }
    const precio = parseFloat(precioExtra);
    if (isNaN(precio) || precio <= 0) {
      alert("Indica un precio mayor a 0 o desmarca «Tiene costo»");
      return null;
    }
    return {
      cantidad: 1,
      costo_unitario: 0,
      usar_precio_manual: true,
      precio_personalizado: precio,
    };
  };

  const handleSave = async (ev) => {
    ev.preventDefault();
    const precioData = buildPayloadPrecio();
    if (!precioData) return;

    if (modoModal === "insumo") {
      if (!insumoSel) {
        alert("Selecciona un insumo para importar");
        return;
      }
      try {
        await createExtraDesdeInsumo(Number(insumoSel), {
          ...precioData,
          tipo,
          activo,
        });
        setShowModal(false);
        resetForm();
        await loadExtras();
      } catch (err) {
        const d = err.response?.data?.detail;
        alert(Array.isArray(d) ? d.map((x) => x.msg).join(", ") : d || "Error al importar");
      }
      return;
    }

    if (!nombre.trim()) {
      alert("El nombre es obligatorio");
      return;
    }

    const payload = {
      nombre: nombre.trim(),
      unidad: unidad.trim() || null,
      ...precioData,
      tipo,
      activo,
    };

    try {
      if (editing) {
        await updateExtra(editing.id_extra, payload);
      } else {
        await createExtra(payload);
      }
      setShowModal(false);
      resetForm();
      await loadExtras();
    } catch (err) {
      const d = err.response?.data?.detail;
      alert(Array.isArray(d) ? d.map((x) => x.msg).join(", ") : d || "Error al guardar");
    }
  };

  const handleDelete = async (e) => {
    if (!window.confirm(`¿Eliminar "${e.nombre}" del catálogo de extras?`)) return;
    try {
      await deleteExtra(e.id_extra);
      await loadExtras();
      if (productoSel) {
        const cfg = await getProductoExtrasConfig(Number(productoSel));
        setIdsEnlazados(cfg.ids_extras || []);
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar");
    }
  };

  const toggleEnlace = (idExtra) => {
    setIdsEnlazados((prev) =>
      prev.includes(idExtra) ? prev.filter((id) => id !== idExtra) : [...prev, idExtra]
    );
  };

  const guardarEnlaces = async () => {
    if (!productoSel) return alert("Selecciona un producto");
    try {
      await saveProductoExtrasConfig(Number(productoSel), idsEnlazados);
      alert("Extras asignados al producto.");
    } catch (err) {
      alert(err.response?.data?.detail || "Error al guardar enlaces");
    }
  };

  const extrasActivos = extras.filter((e) => e.activo);

  const camposPrecio = (
    <>
      <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <input
          type="checkbox"
          checked={tieneCosto}
          onChange={(e) => {
            setTieneCosto(e.target.checked);
            if (!e.target.checked) setPrecioExtra("");
          }}
        />
        Tiene costo adicional
      </label>
      {tieneCosto && (
        <div className="form-row">
          <label>Precio *</label>
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={precioExtra}
            onChange={(e) => setPrecioExtra(e.target.value)}
            placeholder="Ej. 15.00"
            required
          />
        </div>
      )}
      <p className="hint" style={{ marginTop: 0 }}>
        {tieneCosto
          ? <>Se cobrará <strong>${precioPreview.toFixed(2)}</strong> al agregarlo en venta.</>
          : <>Sin costo: solo aparece el nombre en venta.</>}
      </p>
    </>
  );

  if (loading) return <div className="loading-state">Cargando…</div>;

  return (
    <div className="page">
      <PageHeader
        title="Extras de venta"
        subtitle="Catálogo de extras: nombre y si lleva costo al vender"
      />

      <div className="grid-2">
        <section className="card">
          <div className="table-toolbar">
            <h2 style={{ margin: 0 }}>Catálogo</h2>
            <div className="btn-group">
              <button type="button" className="btn btn--secondary" onClick={openNewFromInsumo}>
                Importar insumo
              </button>
              <button type="button" className="btn btn--primary" onClick={openNewManual}>
                Nuevo extra
              </button>
            </div>
          </div>
          <p className="hint" style={{ marginTop: 0 }}>
            Define el nombre y si el extra tiene costo al agregarlo en una venta.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Costo</th>
                  <th>Tipo</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {extras.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="empty-state">
                      Sin extras. Crea uno manual o importa desde insumos.
                    </td>
                  </tr>
                ) : (
                  extras.map((e) => (
                    <tr key={e.id_extra}>
                      <td>
                        {e.nombre}
                        {e.id_insumo_origen && (
                          <span className="hint" style={{ display: "block", fontSize: "0.8rem" }}>
                            Insumo #{e.id_insumo_origen}
                          </span>
                        )}
                      </td>
                      <td>
                        {Number(e.precio) > 0 ? (
                          <>${Number(e.precio).toFixed(2)}</>
                        ) : (
                          <span className="hint">Sin costo</span>
                        )}
                      </td>
                      <td>{e.tipo}</td>
                      <td>
                        <span className={e.activo ? "badge badge--ok" : "badge badge--off"}>
                          {e.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td>
                        <div className="btn-group">
                          <button
                            type="button"
                            className="btn btn--secondary btn--sm"
                            onClick={() => openEdit(e)}
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            className="btn btn--danger btn--sm"
                            onClick={() => handleDelete(e)}
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
        </section>

        <section className="card panel-muted">
          <h2>Asignar por producto</h2>
          <div className="form-row">
            <label>Producto</label>
            <select
              className="select"
              value={productoSel}
              onChange={(e) => setProductoSel(e.target.value)}
            >
              <option value="">Seleccione producto…</option>
              {productos.map((p) => (
                <option key={p.id_producto} value={p.id_producto}>
                  {p.nombre}
                </option>
              ))}
            </select>
          </div>

          {productoSel && (
            <>
              <p className="hint">
                Marca los extras que aplican a este producto en ventas:
              </p>
              <div style={{ maxHeight: 320, overflowY: "auto" }}>
                {extrasActivos.length === 0 ? (
                  <p className="empty-state">No hay extras activos en el catálogo.</p>
                ) : (
                  extrasActivos.map((e) => (
                    <label
                      key={e.id_extra}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        padding: "0.4rem 0",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={idsEnlazados.includes(e.id_extra)}
                        onChange={() => toggleEnlace(e.id_extra)}
                      />
                      <span>
                        {e.nombre} ({e.tipo})
                        {Number(e.precio) > 0 && (
                          <span className="hint"> — ${Number(e.precio).toFixed(2)}</span>
                        )}
                      </span>
                    </label>
                  ))
                )}
              </div>
              <button
                type="button"
                className="btn btn--accent"
                style={{ marginTop: "1rem" }}
                onClick={guardarEnlaces}
              >
                Guardar en producto
              </button>
            </>
          )}
        </section>
      </div>

      {showModal && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h2>
              {modoModal === "edit"
                ? "Editar extra"
                : modoModal === "insumo"
                  ? "Importar desde insumo"
                  : "Nuevo extra manual"}
            </h2>
            <form onSubmit={handleSave}>
              {modoModal === "insumo" && (
                <div className="form-row">
                  <label>Insumo (copia al catálogo)</label>
                  <select
                    className="select"
                    value={insumoSel}
                    onChange={(e) => onInsumoSelect(e.target.value)}
                    required
                  >
                    <option value="">Seleccione…</option>
                    {insumosImportables.map((i) => (
                      <option key={i.id_insumo} value={i.id_insumo}>
                        {i.nombre} — ${Number(i.costo_unitario).toFixed(2)}/{i.unidad}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {(modoModal === "manual" || modoModal === "edit") && (
                <>
                  <div className="form-row">
                    <label>Nombre *</label>
                    <input value={nombre} onChange={(e) => setNombre(e.target.value)} required />
                  </div>
                  <div className="form-row">
                    <label>Unidad</label>
                    <input value={unidad} onChange={(e) => setUnidad(e.target.value)} />
                  </div>
                </>
              )}

              {modoModal === "insumo" && insumoSel && (
                <p className="hint">
                  <strong>{nombre}</strong> ({unidad})
                </p>
              )}

              {camposPrecio}

              <div className="form-row">
                <label>Tipo en POS</label>
                <select className="select" value={tipo} onChange={(e) => setTipo(e.target.value)}>
                  {TIPOS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={activo}
                  onChange={(e) => setActivo(e.target.checked)}
                />
                Activo en catálogo
              </label>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => {
                    setShowModal(false);
                    resetForm();
                  }}
                >
                  Cancelar
                </button>
                <button type="submit" className="btn btn--primary">
                  {modoModal === "insumo" ? "Importar" : editing ? "Actualizar" : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
