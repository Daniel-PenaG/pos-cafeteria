import { useEffect, useMemo, useState } from "react";
import {
  getExtrasCatalogo,
  getInsumosImportables,
  createExtra,
  createExtraDesdeInsumo,
  updateExtra,
  deleteExtra,
  getCategoriaExtrasConfig,
  saveCategoriaExtrasConfig,
} from "../services/extrasVentaService";
import { getCategorias } from "../services/categoriasService";
import PageHeader from "../components/PageHeader";

const TIPOS = [
  { value: "CAFE", label: "Café" },
  { value: "LECHE", label: "Leche" },
  { value: "SABORIZANTE", label: "Saborizante" },
  { value: "OTRO", label: "Otro" },
];

function precioCalculado(costo, cantidad) {
  return (parseFloat(costo) || 0) * (parseFloat(cantidad) || 1);
}

export default function ExtrasVenta() {
  const [extras, setExtras] = useState([]);
  const [insumosImportables, setInsumosImportables] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [categoriaSel, setCategoriaSel] = useState("");
  const [idsEnlazados, setIdsEnlazados] = useState([]);
  const [loading, setLoading] = useState(false);

  const [showModal, setShowModal] = useState(false);
  const [modoModal, setModoModal] = useState("manual");
  const [editing, setEditing] = useState(null);
  const [nombre, setNombre] = useState("");
  const [unidad, setUnidad] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [costoUnitario, setCostoUnitario] = useState("0");
  const [usarPrecioManual, setUsarPrecioManual] = useState(false);
  const [precioPersonalizado, setPrecioPersonalizado] = useState("");
  const [tipo, setTipo] = useState("OTRO");
  const [activo, setActivo] = useState(true);
  const [insumoSel, setInsumoSel] = useState("");

  const precioPreview = useMemo(() => {
    if (usarPrecioManual) {
      const p = parseFloat(precioPersonalizado);
      return isNaN(p) ? 0 : p;
    }
    return precioCalculado(costoUnitario, cantidad);
  }, [usarPrecioManual, precioPersonalizado, costoUnitario, cantidad]);

  const loadExtras = async () => {
    const data = await getExtrasCatalogo();
    setExtras(data);
  };

  const loadCategorias = async () => {
    const data = await getCategorias();
    setCategorias(data);
  };

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        await Promise.all([loadExtras(), loadCategorias()]);
      } catch (err) {
        console.error(err);
        alert("Error al cargar datos");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!categoriaSel) {
      setIdsEnlazados([]);
      return;
    }
    (async () => {
      try {
        const cfg = await getCategoriaExtrasConfig(Number(categoriaSel));
        setIdsEnlazados(cfg.ids_extras || []);
      } catch (err) {
        console.error(err);
        alert("Error al cargar configuración de categoría");
      }
    })();
  }, [categoriaSel]);

  const resetForm = () => {
    setNombre("");
    setUnidad("");
    setCantidad("1");
    setCostoUnitario("0");
    setUsarPrecioManual(false);
    setPrecioPersonalizado("");
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
    setCantidad(String(e.cantidad ?? 1));
    setCostoUnitario(String(e.costo_unitario ?? 0));
    setUsarPrecioManual(!!e.usar_precio_manual);
    setPrecioPersonalizado(
      e.precio_personalizado != null ? String(e.precio_personalizado) : String(e.precio)
    );
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
      setCostoUnitario(String(ins.costo_unitario));
      setCantidad("1");
      setUsarPrecioManual(false);
    }
  };

  const buildPayloadPrecio = () => {
    const cant = parseFloat(cantidad);
    const costo = parseFloat(costoUnitario);
    if (isNaN(cant) || cant <= 0) {
      alert("La cantidad debe ser mayor a 0");
      return null;
    }
    if (isNaN(costo) || costo < 0) {
      alert("Indica un costo unitario válido");
      return null;
    }
    let precioPers = null;
    if (usarPrecioManual) {
      precioPers = parseFloat(precioPersonalizado);
      if (isNaN(precioPers) || precioPers < 0) {
        alert("Indica un precio personalizado válido");
        return null;
      }
    }
    return {
      cantidad: cant,
      costo_unitario: costo,
      usar_precio_manual: usarPrecioManual,
      precio_personalizado: precioPers,
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
      if (categoriaSel) {
        const cfg = await getCategoriaExtrasConfig(Number(categoriaSel));
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
    if (!categoriaSel) return alert("Selecciona una categoría");
    try {
      await saveCategoriaExtrasConfig(Number(categoriaSel), idsEnlazados);
      alert("Enlaces guardados.");
    } catch (err) {
      alert(err.response?.data?.detail || "Error al guardar enlaces");
    }
  };

  const extrasActivos = extras.filter((e) => e.activo);

  const camposPrecio = (
    <>
      <div className="form-grid">
        <div className="form-row">
          <label>Cantidad</label>
          <input
            type="number"
            min="0.001"
            step="0.001"
            value={cantidad}
            onChange={(e) => setCantidad(e.target.value)}
            required
          />
        </div>
        <div className="form-row">
          <label>Costo unitario (ref.)</label>
          <input
            type="number"
            min="0"
            step="0.0001"
            value={costoUnitario}
            onChange={(e) => setCostoUnitario(e.target.value)}
            required
          />
        </div>
      </div>
      <p className="hint">
        Precio calculado: <strong>${precioCalculado(costoUnitario, cantidad).toFixed(2)}</strong>
        {" "}(costo × cantidad)
      </p>
      <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <input
          type="checkbox"
          checked={usarPrecioManual}
          onChange={(e) => setUsarPrecioManual(e.target.checked)}
        />
        Usar precio personalizado
      </label>
      {usarPrecioManual && (
        <div className="form-row">
          <label>Precio de venta *</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={precioPersonalizado}
            onChange={(e) => setPrecioPersonalizado(e.target.value)}
            required
          />
        </div>
      )}
      <p className="hint" style={{ marginTop: 0 }}>
        Precio en POS: <strong>${precioPreview.toFixed(2)}</strong>
      </p>
    </>
  );

  if (loading) return <div className="loading-state">Cargando…</div>;

  return (
    <div className="page">
      <PageHeader
        title="Extras de venta"
        subtitle="Catálogo propio con precio por cantidad (costo × cant.) o precio fijo que definas"
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
            El precio de venta es costo unitario × cantidad, salvo que actives precio personalizado.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Cant.</th>
                  <th>Costo u.</th>
                  <th>Precio venta</th>
                  <th>Tipo</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {extras.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="empty-state">
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
                      <td>{Number(e.cantidad).toFixed(3)}</td>
                      <td>${Number(e.costo_unitario).toFixed(2)}</td>
                      <td>
                        ${Number(e.precio).toFixed(2)}
                        {e.usar_precio_manual && (
                          <span className="badge" style={{ marginLeft: "0.35rem" }}>
                            fijo
                          </span>
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
          <h2>Enlazar por categoría</h2>
          <div className="form-row">
            <label>Categoría de producto</label>
            <select
              className="select"
              value={categoriaSel}
              onChange={(e) => setCategoriaSel(e.target.value)}
            >
              <option value="">Seleccione categoría…</option>
              {categorias.map((c) => (
                <option key={c.id_categoria} value={c.id_categoria}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </div>

          {categoriaSel && (
            <>
              <p className="hint">Extras del catálogo para productos de esta categoría:</p>
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
                        {e.nombre} ({e.tipo}) — ${Number(e.precio).toFixed(2)}
                        {!e.usar_precio_manual && (
                          <span className="hint">
                            {" "}
                            ({Number(e.cantidad)} × ${Number(e.costo_unitario).toFixed(2)})
                          </span>
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
                Guardar enlaces
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
