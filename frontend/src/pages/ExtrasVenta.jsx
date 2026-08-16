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
  getExtraTiposPos,
  createExtraTipoPos,
} from "../services/extrasVentaService";
import { getProductos } from "../services/productosService";
import PageHeader from "../components/PageHeader";

export default function ExtrasVenta() {
  const [extras, setExtras] = useState([]);
  const [tiposPos, setTiposPos] = useState([]);
  const [nuevoTipoNombre, setNuevoTipoNombre] = useState("");
  const [agregandoTipo, setAgregandoTipo] = useState(false);
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
  const [cantidadInsumo, setCantidadInsumo] = useState("");

  const precioPreview = useMemo(() => {
    if (!tieneCosto) return 0;
    const p = parseFloat(precioExtra);
    return isNaN(p) ? 0 : p;
  }, [tieneCosto, precioExtra]);

  const loadExtras = async () => {
    const data = await getExtrasCatalogo();
    setExtras(data);
  };

  const loadTiposPos = async () => {
    const data = await getExtraTiposPos();
    setTiposPos(data);
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
        await Promise.all([loadExtras(), loadProductos(), loadTiposPos()]);
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
    setCantidadInsumo("");
    setEditing(null);
    setModoModal("manual");
  };

  const openNewManual = async () => {
    resetForm();
    setModoModal("manual");
    try {
      const lista = await getInsumosImportables();
      setInsumosImportables(lista);
      setShowModal(true);
    } catch (err) {
      alert(err.response?.data?.detail || "Error al cargar insumos");
    }
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

  const openEdit = async (e) => {
    setEditing(e);
    setModoModal("edit");
    setNombre(e.nombre);
    setUnidad(e.unidad || "");
    const precio = Number(e.precio) || 0;
    setTieneCosto(precio > 0);
    setPrecioExtra(precio > 0 ? String(precio) : "");
    setTipo(e.tipo || "OTRO");
    setActivo(e.activo !== false);
    setInsumoSel(e.id_insumo_origen ? String(e.id_insumo_origen) : "");
    setCantidadInsumo(
      e.cantidad != null && Number(e.cantidad) !== 0 ? String(e.cantidad) : ""
    );
    try {
      const lista = await getInsumosImportables();
      setInsumosImportables(lista);
      setShowModal(true);
    } catch (err) {
      alert(err.response?.data?.detail || "Error al cargar insumos");
    }
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
    const cantidad = parseFloat(cantidadInsumo);
    if (isNaN(cantidad) || cantidad <= 0) {
      alert("Indica una cantidad de insumo mayor a 0");
      return null;
    }
    if (!tieneCosto) {
      return {
        cantidad,
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
      cantidad,
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
    if (!insumoSel) {
      alert("Selecciona el insumo del que se descontará inventario");
      return;
    }

    const payload = {
      nombre: nombre.trim(),
      unidad: unidad.trim() || null,
      id_insumo_origen: Number(insumoSel),
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

  const quitarEnlace = (idExtra) => {
    setIdsEnlazados((prev) => prev.filter((id) => id !== idExtra));
  };

  const agregarEnlace = (idExtra) => {
    setIdsEnlazados((prev) => {
      if (prev.includes(idExtra)) return prev;
      return [...prev, idExtra];
    });
  };

  const onDragStartExtra = (ev, idExtra) => {
    ev.dataTransfer.setData("text/extra-id", String(idExtra));
    ev.dataTransfer.effectAllowed = "copy";
  };

  const onDropEnProducto = (ev) => {
    ev.preventDefault();
    const id = Number(ev.dataTransfer.getData("text/extra-id"));
    if (id) agregarEnlace(id);
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

  const handleAgregarTipo = async (ev) => {
    ev?.preventDefault?.();
    const nombre = nuevoTipoNombre.trim();
    if (!nombre) return alert("Escribe el nombre de la categoría");
    try {
      setAgregandoTipo(true);
      const creado = await createExtraTipoPos(nombre);
      await loadTiposPos();
      setTipo(creado.codigo);
      setNuevoTipoNombre("");
    } catch (err) {
      alert(err.response?.data?.detail || "Error al crear categoría");
    } finally {
      setAgregandoTipo(false);
    }
  };

  const extrasActivos = extras.filter((e) => e.activo);

  const extrasAsignados = useMemo(
    () =>
      idsEnlazados
        .map((id) => extrasActivos.find((e) => e.id_extra === id))
        .filter(Boolean),
    [idsEnlazados, extrasActivos]
  );

  const extrasDisponibles = useMemo(
    () => extrasActivos.filter((e) => !idsEnlazados.includes(e.id_extra)),
    [extrasActivos, idsEnlazados]
  );

  const productoNombre = productos.find(
    (p) => String(p.id_producto) === String(productoSel)
  )?.nombre;

  const etiquetaTipo = (codigo) =>
    tiposPos.find((t) => t.codigo === codigo)?.etiqueta || codigo;

  const camposPrecio = (
    <>
      <div className="form-row">
        <label>Cantidad de insumo por extra *</label>
        <input
          type="number"
          min="0.001"
          step="0.001"
          value={cantidadInsumo}
          onChange={(e) => setCantidadInsumo(e.target.value)}
          required
        />
        <p className="hint" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
          Se descuenta del inventario por cada unidad del producto vendido.
        </p>
      </div>
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
          : <>Sin costo al cliente, pero sí descuenta inventario del insumo.</>}
      </p>
    </>
  );

  if (loading) return <div className="loading-state">Cargando…</div>;

  return (
    <div className="page">
      <PageHeader
        title="Extras de venta"
        subtitle="Catálogo de extras ligados a insumos: precio en venta y descuento de inventario"
      />

      <section className="card extras-tipos-panel">
        <h2 style={{ marginTop: 0 }}>Tipos en POS</h2>
        <p className="hint" style={{ marginTop: 0 }}>
          Categorías para agrupar extras en ventas (Café, Leche, etc.). Agrega las que necesites.
        </p>
        <div className="extras-tipos-list">
          {tiposPos.map((t) => (
            <span key={t.codigo} className="extra-tipo-badge">
              {t.etiqueta}
            </span>
          ))}
        </div>
        <form className="extras-tipos-form" onSubmit={handleAgregarTipo}>
          <div className="form-row" style={{ marginBottom: 0, flex: 1 }}>
            <label htmlFor="nuevo-tipo-pos">Nueva categoría</label>
            <input
              id="nuevo-tipo-pos"
              value={nuevoTipoNombre}
              onChange={(e) => setNuevoTipoNombre(e.target.value)}
              placeholder="Ej. Jarabe, Topping…"
            />
          </div>
          <button
            type="submit"
            className="btn btn--secondary"
            disabled={agregandoTipo || !nuevoTipoNombre.trim()}
          >
            {agregandoTipo ? "Agregando…" : "Agregar categoría"}
          </button>
        </form>
      </section>

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
            Cada extra debe estar ligado a un insumo. Al venderse descuenta stock en mesa y para llevar.
            {productoSel && (
              <>
                {" "}
                Arrastra un extra hacia el panel de la derecha para asignarlo a{" "}
                <strong>{productoNombre}</strong>.
              </>
            )}
          </p>
          {productoSel && extrasDisponibles.length > 0 && (
            <div className="extras-drag-source">
              <p className="hint" style={{ marginBottom: "0.5rem" }}>
                Catálogo disponible (arrastra →)
              </p>
              <div className="extras-drag-list">
                {extrasDisponibles.map((e) => (
                  <div
                    key={e.id_extra}
                    className="extra-drag-chip"
                    draggable
                    onDragStart={(ev) => onDragStartExtra(ev, e.id_extra)}
                    title="Arrastra al producto"
                  >
                    {e.nombre}
                    {Number(e.precio) > 0 && (
                      <span className="hint"> ${Number(e.precio).toFixed(2)}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {productoSel && extrasDisponibles.length === 0 && extrasActivos.length > 0 && (
            <p className="hint">Todos los extras activos ya están en este producto.</p>
          )}
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
                      <td>{etiquetaTipo(e.tipo)}</td>
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

          {productoSel ? (
            <>
              <p className="hint">
                Arrastra extras desde el catálogo (izquierda) o suelta aquí:
              </p>
              <div
                className="extras-drop-zone"
                onDragOver={(ev) => ev.preventDefault()}
                onDrop={onDropEnProducto}
              >
                {extrasAsignados.length === 0 ? (
                  <p className="empty-state extras-drop-zone__empty">
                    Sin extras — arrastra desde el catálogo
                  </p>
                ) : (
                  <ul className="extras-asignados-list">
                    {extrasAsignados.map((e) => (
                      <li key={e.id_extra} className="extra-asignado-item">
                        <span>
                          {e.nombre}
                          {Number(e.precio) > 0 && (
                            <span className="hint"> — ${Number(e.precio).toFixed(2)}</span>
                          )}
                        </span>
                        <button
                          type="button"
                          className="btn btn--danger btn--sm"
                          onClick={() => quitarEnlace(e.id_extra)}
                          title="Quitar"
                        >
                          ✕
                        </button>
                      </li>
                    ))}
                  </ul>
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
          ) : (
            <p className="hint">Selecciona un producto para asignar extras.</p>
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
                    <label>Insumo (inventario) *</label>
                    <select
                      className="select"
                      value={insumoSel}
                      onChange={(e) => {
                        const id = e.target.value;
                        setInsumoSel(id);
                        const ins = insumosImportables.find(
                          (i) => String(i.id_insumo) === String(id)
                        );
                        if (ins && modoModal === "manual") {
                          setNombre(ins.nombre);
                          setUnidad(ins.unidad);
                        }
                      }}
                      required
                    >
                      <option value="">Seleccione insumo…</option>
                      {insumosImportables.map((i) => (
                        <option key={i.id_insumo} value={i.id_insumo}>
                          {i.nombre} — stock en {i.unidad}
                        </option>
                      ))}
                    </select>
                  </div>
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
                  {tiposPos.map((t) => (
                    <option key={t.codigo} value={t.codigo}>
                      {t.etiqueta}
                    </option>
                  ))}
                </select>
              </div>
              <div className="extras-tipos-inline">
                <input
                  value={nuevoTipoNombre}
                  onChange={(e) => setNuevoTipoNombre(e.target.value)}
                  placeholder="Nueva categoría…"
                />
                <button
                  type="button"
                  className="btn btn--secondary btn--sm"
                  disabled={agregandoTipo || !nuevoTipoNombre.trim()}
                  onClick={handleAgregarTipo}
                >
                  +
                </button>
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
