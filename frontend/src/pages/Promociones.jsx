import { useEffect, useState } from "react";
import {
  getPromociones,
  getPromocionesResumen,
  createPromocion,
  updatePromocion,
  deletePromocion,
} from "../services/promocionesService";
import { getProductos } from "../services/productosService";
import { getCategorias } from "../services/categoriasService";
import PageHeader from "../components/PageHeader";

const TIPOS = [
  { value: "PORCENTAJE", label: "% Descuento" },
  { value: "PRECIO_FIJO", label: "Precio fijo" },
  { value: "DOS_X_UNO", label: "2×1" },
];

const DIAS = [
  { v: 0, l: "Lun" },
  { v: 1, l: "Mar" },
  { v: 2, l: "Mié" },
  { v: 3, l: "Jue" },
  { v: 4, l: "Vie" },
  { v: 5, l: "Sáb" },
  { v: 6, l: "Dom" },
];

function toLocalDatetime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalDatetime(val) {
  if (!val) return null;
  return new Date(val).toISOString();
}

function formatVigenciaPromo(p) {
  const partes = [];
  if (p.dias_semana) {
    const labels = p.dias_semana
      .split(",")
      .map((d) => DIAS.find((x) => x.v === Number(d.trim()))?.l)
      .filter(Boolean);
    if (labels.length) partes.push(labels.join(", "));
  }
  if (p.hora_inicio || p.hora_fin) {
    partes.push(`${p.hora_inicio || "00:00"} – ${p.hora_fin || "23:59"}`);
  }
  if (p.fecha_inicio || p.fecha_fin) {
    const fi = p.fecha_inicio ? new Date(p.fecha_inicio).toLocaleDateString() : "…";
    const ff = p.fecha_fin ? new Date(p.fecha_fin).toLocaleDateString() : "…";
    partes.push(`${fi} → ${ff}`);
  }
  return partes.length ? partes.join(" · ") : "Siempre";
}

export default function Promociones() {
  const [promos, setPromos] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);

  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [tipo, setTipo] = useState("PORCENTAJE");
  const [valor, setValor] = useState("");
  const [activa, setActiva] = useState(true);
  const [todaTienda, setTodaTienda] = useState(false);
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");
  const [horaInicio, setHoraInicio] = useState("");
  const [horaFin, setHoraFin] = useState("");
  const [diasSel, setDiasSel] = useState([]);
  const [usarDiasSemana, setUsarDiasSemana] = useState(false);
  const [usarHorario, setUsarHorario] = useState(false);
  const [usarVigenciaFechas, setUsarVigenciaFechas] = useState(false);
  const [margenMinimo, setMargenMinimo] = useState("");
  const [idsProductos, setIdsProductos] = useState([]);
  const [idsCategorias, setIdsCategorias] = useState([]);

  const load = async () => {
    try {
      setLoading(true);
      const [p, r, prods, cats] = await Promise.all([
        getPromociones(),
        getPromocionesResumen(),
        getProductos(),
        getCategorias(),
      ]);
      setPromos(p);
      setResumen(r);
      setProductos(prods.filter((x) => x.activo !== false));
      setCategorias(cats);
    } catch (err) {
      console.error(err);
      alert("Error al cargar promociones");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const resetForm = () => {
    setNombre("");
    setDescripcion("");
    setTipo("PORCENTAJE");
    setValor("");
    setActiva(true);
    setTodaTienda(false);
    setFechaInicio("");
    setFechaFin("");
    setHoraInicio("");
    setHoraFin("");
    setDiasSel([]);
    setUsarDiasSemana(false);
    setUsarHorario(false);
    setUsarVigenciaFechas(false);
    setMargenMinimo("");
    setIdsProductos([]);
    setIdsCategorias([]);
    setEditing(null);
  };

  const openNew = () => {
    resetForm();
    setShowModal(true);
  };

  const openEdit = (p) => {
    setEditing(p);
    setNombre(p.nombre);
    setDescripcion(p.descripcion || "");
    setTipo(p.tipo);
    setValor(String(p.valor));
    setActiva(p.activa !== false);
    setTodaTienda(!!p.aplica_toda_tienda);
    setFechaInicio(toLocalDatetime(p.fecha_inicio));
    setFechaFin(toLocalDatetime(p.fecha_fin));
    setHoraInicio(p.hora_inicio || "");
    setHoraFin(p.hora_fin || "");
    setDiasSel(p.dias_semana ? p.dias_semana.split(",").map(Number) : []);
    setUsarDiasSemana(!!p.dias_semana);
    setUsarHorario(!!(p.hora_inicio || p.hora_fin));
    setUsarVigenciaFechas(!!(p.fecha_inicio || p.fecha_fin));
    setMargenMinimo(p.margen_minimo != null ? String(p.margen_minimo) : "");
    setIdsProductos(p.ids_productos || []);
    setIdsCategorias(p.ids_categorias || []);
    setShowModal(true);
  };

  const toggleDia = (d) => {
    setDiasSel((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]));
  };

  const toggleId = (list, setList, id) => {
    setList((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const buildPayload = () => {
    let v = parseFloat(valor);
    if (tipo === "DOS_X_UNO") v = 2;
    if (!nombre.trim()) {
      alert("El nombre es obligatorio");
      return null;
    }
    if (isNaN(v) || v <= 0) {
      alert("Indica un valor válido");
      return null;
    }
    if (tipo === "PORCENTAJE" && v > 100) {
      alert("El porcentaje no puede ser mayor a 100");
      return null;
    }
    if (!todaTienda && idsProductos.length === 0 && idsCategorias.length === 0) {
      alert("Selecciona productos, categorías o marca toda la tienda");
      return null;
    }
    if (usarDiasSemana && diasSel.length === 0) {
      alert("Selecciona al menos un día de la semana");
      return null;
    }
    if (usarHorario && (!horaInicio || !horaFin)) {
      alert("Indica hora de inicio y hora de fin");
      return null;
    }
    return {
      nombre: nombre.trim(),
      descripcion: descripcion.trim() || null,
      tipo,
      valor: v,
      activa,
      aplica_toda_tienda: todaTienda,
      fecha_inicio: usarVigenciaFechas ? fromLocalDatetime(fechaInicio) : null,
      fecha_fin: usarVigenciaFechas ? fromLocalDatetime(fechaFin) : null,
      hora_inicio: usarHorario ? horaInicio : null,
      hora_fin: usarHorario ? horaFin : null,
      dias_semana: usarDiasSemana && diasSel.length ? diasSel.sort((a, b) => a - b).join(",") : null,
      margen_minimo: margenMinimo !== "" ? parseFloat(margenMinimo) : null,
      ids_productos: todaTienda ? [] : idsProductos,
      ids_categorias: todaTienda ? [] : idsCategorias,
    };
  };

  const handleSave = async (e) => {
    e.preventDefault();
    const payload = buildPayload();
    if (!payload) return;
    try {
      if (editing) {
        await updatePromocion(editing.id_promocion, payload);
      } else {
        await createPromocion(payload);
      }
      setShowModal(false);
      resetForm();
      await load();
    } catch (err) {
      const d = err.response?.data?.detail;
      alert(Array.isArray(d) ? d.map((x) => x.msg).join(", ") : d || "Error al guardar");
    }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`¿Eliminar promoción "${p.nombre}"?`)) return;
    try {
      await deletePromocion(p.id_promocion);
      await load();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar");
    }
  };

  const tipoLabel = (t) => TIPOS.find((x) => x.value === t)?.label || t;

  if (loading) return <div className="loading-state">Cargando…</div>;

  return (
    <div className="page">
      <PageHeader
        title="Promociones"
        subtitle="Descuentos con control de margen según costo de receta"
      />

      {resumen && (
        <section className="card panel-muted" style={{ marginBottom: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>Resumen</h2>
          <p className="hint">
            Líneas vendidas con promo: <strong>{resumen.total_ventas_con_promo}</strong> · Descuento
            total: <strong>${Number(resumen.total_descuento).toFixed(2)}</strong>
          </p>
        </section>
      )}

      <section className="card">
        <div className="table-toolbar">
          <h2 style={{ margin: 0 }}>Catálogo</h2>
          <button type="button" className="btn btn--primary" onClick={openNew}>
            Nueva promoción
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Tipo</th>
                <th>Valor</th>
                <th>Alcance</th>
                <th>Vigencia</th>
                <th>Margen mín.</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {promos.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty-state">
                    Sin promociones
                  </td>
                </tr>
              ) : (
                promos.map((p) => (
                  <tr key={p.id_promocion}>
                    <td>{p.nombre}</td>
                    <td>{tipoLabel(p.tipo)}</td>
                    <td>
                      {p.tipo === "PORCENTAJE"
                        ? `${p.valor}%`
                        : p.tipo === "PRECIO_FIJO"
                          ? `$${Number(p.valor).toFixed(2)}`
                          : "2×1"}
                    </td>
                    <td>
                      {p.aplica_toda_tienda
                        ? "Toda la tienda"
                        : `${(p.ids_productos || []).length} prod. · ${(p.ids_categorias || []).length} cat.`}
                    </td>
                    <td className="promo-vigencia-cell">{formatVigenciaPromo(p)}</td>
                    <td>{p.margen_minimo != null ? `${p.margen_minimo}%` : "—"}</td>
                    <td>
                      <span className={p.activa ? "badge badge--ok" : "badge badge--off"}>
                        {p.activa ? "Activa" : "Inactiva"}
                      </span>
                    </td>
                    <td>
                      <div className="btn-group">
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm"
                          onClick={() => openEdit(p)}
                        >
                          Editar
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
      </section>

      {showModal && (
        <div className="modal-overlay">
          <div className="modal-box modal-box--wide">
            <h2>{editing ? "Editar promoción" : "Nueva promoción"}</h2>
            <form onSubmit={handleSave}>
              <div className="form-row">
                <label>Nombre *</label>
                <input value={nombre} onChange={(e) => setNombre(e.target.value)} required />
              </div>
              <div className="form-row">
                <label>Descripción</label>
                <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
              </div>
              <div className="form-grid">
                <div className="form-row">
                  <label>Tipo *</label>
                  <select className="select" value={tipo} onChange={(e) => setTipo(e.target.value)}>
                    {TIPOS.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-row">
                  <label>Valor *</label>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={tipo === "DOS_X_UNO" ? "2" : valor}
                    onChange={(e) => setValor(e.target.value)}
                    required
                    disabled={tipo === "DOS_X_UNO"}
                  />
                </div>
              </div>
              <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={todaTienda}
                  onChange={(e) => setTodaTienda(e.target.checked)}
                />
                Aplica a toda la tienda
              </label>
              {!todaTienda && (
                <>
                  <p className="hint">Productos:</p>
                  <div style={{ maxHeight: 100, overflowY: "auto" }}>
                    {productos.map((p) => (
                      <label key={p.id_producto} style={{ display: "block" }}>
                        <input
                          type="checkbox"
                          checked={idsProductos.includes(p.id_producto)}
                          onChange={() => toggleId(idsProductos, setIdsProductos, p.id_producto)}
                        />{" "}
                        {p.nombre}
                      </label>
                    ))}
                  </div>
                  <p className="hint">Categorías:</p>
                  <div style={{ maxHeight: 80, overflowY: "auto" }}>
                    {categorias.map((c) => (
                      <label key={c.id_categoria} style={{ display: "block" }}>
                        <input
                          type="checkbox"
                          checked={idsCategorias.includes(c.id_categoria)}
                          onChange={() =>
                            toggleId(idsCategorias, setIdsCategorias, c.id_categoria)
                          }
                        />{" "}
                        {c.nombre}
                      </label>
                    ))}
                  </div>
                </>
              )}
              <div className="form-row">
                <label>Margen mínimo (%)</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={margenMinimo}
                  onChange={(e) => setMargenMinimo(e.target.value)}
                />
              </div>

              <fieldset className="promo-fieldset">
                <legend>Vigencia y horarios</legend>

                <label className="promo-check">
                  <input
                    type="checkbox"
                    checked={usarDiasSemana}
                    onChange={(e) => {
                      setUsarDiasSemana(e.target.checked);
                      if (!e.target.checked) setDiasSel([]);
                    }}
                  />
                  Solo ciertos días de la semana
                </label>
                {usarDiasSemana && (
                  <div className="promo-dias-chips">
                    {DIAS.map((d) => (
                      <button
                        key={d.v}
                        type="button"
                        className={`extra-chip ${diasSel.includes(d.v) ? "extra-chip--selected" : ""}`}
                        onClick={() => toggleDia(d.v)}
                      >
                        {d.l}
                      </button>
                    ))}
                  </div>
                )}

                <label className="promo-check">
                  <input
                    type="checkbox"
                    checked={usarHorario}
                    onChange={(e) => {
                      setUsarHorario(e.target.checked);
                      if (!e.target.checked) {
                        setHoraInicio("");
                        setHoraFin("");
                      }
                    }}
                  />
                  Limitar por horario (hora inicio y fin)
                </label>
                {usarHorario && (
                  <div className="form-grid">
                    <div className="form-row">
                      <label>Hora inicio</label>
                      <input
                        type="time"
                        className="input"
                        value={horaInicio}
                        onChange={(e) => setHoraInicio(e.target.value)}
                        required={usarHorario}
                      />
                    </div>
                    <div className="form-row">
                      <label>Hora fin</label>
                      <input
                        type="time"
                        className="input"
                        value={horaFin}
                        onChange={(e) => setHoraFin(e.target.value)}
                        required={usarHorario}
                      />
                    </div>
                  </div>
                )}

                <label className="promo-check">
                  <input
                    type="checkbox"
                    checked={usarVigenciaFechas}
                    onChange={(e) => {
                      setUsarVigenciaFechas(e.target.checked);
                      if (!e.target.checked) {
                        setFechaInicio("");
                        setFechaFin("");
                      }
                    }}
                  />
                  Vigencia por rango de fechas
                </label>
                {usarVigenciaFechas && (
                  <div className="form-grid">
                    <div className="form-row">
                      <label>Desde</label>
                      <input
                        type="datetime-local"
                        className="input"
                        value={fechaInicio}
                        onChange={(e) => setFechaInicio(e.target.value)}
                      />
                    </div>
                    <div className="form-row">
                      <label>Hasta</label>
                      <input
                        type="datetime-local"
                        className="input"
                        value={fechaFin}
                        onChange={(e) => setFechaFin(e.target.value)}
                      />
                    </div>
                  </div>
                )}
              </fieldset>

              <label className="promo-check">
                <input
                  type="checkbox"
                  checked={activa}
                  onChange={(e) => setActiva(e.target.checked)}
                />
                Activa
              </label>
              <div className="modal-footer">
                <button type="button" className="btn btn--secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn--primary">
                  Guardar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
