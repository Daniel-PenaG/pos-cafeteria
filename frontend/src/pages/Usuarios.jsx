import { useEffect, useState, useMemo } from "react";
import PageHeader from "../components/PageHeader";
import {
  getUsuarios,
  getPerfiles,
  getModulosCatalogo,
  createUsuario,
  updateUsuario,
  deleteUsuario,
} from "../services/usuariosService";
import { ROLE_ROUTES } from "../config/permissions";

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState([]);
  const [perfiles, setPerfiles] = useState([]);
  const [catalogo, setCatalogo] = useState({ modulos: [], defaults_por_rol: {} });
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);

  const [nombre, setNombre] = useState("");
  const [usuarioLogin, setUsuarioLogin] = useState("");
  const [password, setPassword] = useState("");
  const [rol, setRol] = useState("CAJERO");
  const [modulosSel, setModulosSel] = useState([]);
  const [usarPersonalizado, setUsarPersonalizado] = useState(false);

  const modulosPorGrupo = useMemo(() => {
    const map = new Map();
    for (const m of catalogo.modulos || []) {
      if (!map.has(m.grupo)) map.set(m.grupo, []);
      map.get(m.grupo).push(m);
    }
    return map;
  }, [catalogo.modulos]);

  const cargar = async () => {
    setLoading(true);
    try {
      const [u, p, cat] = await Promise.all([
        getUsuarios(),
        getPerfiles(),
        getModulosCatalogo(),
      ]);
      setUsuarios(u);
      setPerfiles(p);
      setCatalogo(cat);
    } catch {
      alert("Error al cargar usuarios");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const defaultsRol = (r) =>
    catalogo.defaults_por_rol?.[r] || ROLE_ROUTES[r] || [];

  const abrirNuevo = () => {
    setEditing(null);
    setNombre("");
    setUsuarioLogin("");
    setPassword("");
    setRol("CAJERO");
    setUsarPersonalizado(false);
    setModulosSel(defaultsRol("CAJERO"));
    setShowModal(true);
  };

  const abrirEditar = (u) => {
    setEditing(u);
    setNombre(u.nombre);
    setUsuarioLogin(u.usuario_login);
    setPassword("");
    setRol(u.rol);
    const tieneCustom = Array.isArray(u.modulos) && u.modulos.length > 0;
    setUsarPersonalizado(tieneCustom);
    setModulosSel(
      tieneCustom ? u.modulos : u.modulos_efectivos || defaultsRol(u.rol)
    );
    setShowModal(true);
  };

  const onChangeRol = (nuevoRol) => {
    setRol(nuevoRol);
    if (!usarPersonalizado) {
      setModulosSel(defaultsRol(nuevoRol));
    }
  };

  const toggleModulo = (path) => {
    setModulosSel((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]
    );
  };

  const guardar = async () => {
    if (!nombre.trim() || !usuarioLogin.trim()) {
      alert("Nombre y usuario son obligatorios");
      return;
    }
    if (!editing && !password) {
      alert("La contraseña es obligatoria para usuarios nuevos");
      return;
    }
    if (usarPersonalizado && modulosSel.length === 0) {
      alert("Selecciona al menos un módulo");
      return;
    }

    const modulosPayload = usarPersonalizado ? modulosSel : [];

    try {
      if (editing) {
        const payload = { nombre, rol, modulos: modulosPayload };
        if (password) payload.password = password;
        await updateUsuario(editing.id_usuario, payload);
      } else {
        await createUsuario({
          nombre,
          usuario_login: usuarioLogin,
          password,
          rol,
          modulos: modulosPayload,
        });
      }
      setShowModal(false);
      cargar();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al guardar");
    }
  };

  const eliminar = async (u) => {
    if (!confirm(`¿Eliminar al usuario "${u.nombre}"?`)) return;
    try {
      await deleteUsuario(u.id_usuario);
      cargar();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar");
    }
  };

  const labelRol = (codigo) =>
    perfiles.find((p) => p.codigo === codigo)?.nombre || codigo;

  return (
    <div>
      <PageHeader
        title="Usuarios y perfiles"
        subtitle="Gestiona cuentas, roles y módulos visibles por usuario"
      >
        <button type="button" className="btn btn--accent" onClick={abrirNuevo}>
          + Nuevo usuario
        </button>
      </PageHeader>

      {loading ? (
        <p>Cargando…</p>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Usuario</th>
                <th>Perfil</th>
                <th>Módulos</th>
                <th style={{ width: 140 }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id_usuario}>
                  <td>{u.nombre}</td>
                  <td>{u.usuario_login}</td>
                  <td>
                    <span className="badge">{labelRol(u.rol)}</span>
                  </td>
                  <td>
                    <span className="hint">
                      {u.modulos?.length
                        ? `${u.modulos.length} personalizados`
                        : "Por defecto del rol"}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={() => abrirEditar(u)}
                    >
                      Editar
                    </button>{" "}
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={() => eliminar(u)}
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div
            className="modal modal--wide"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 520, maxHeight: "90vh", overflowY: "auto" }}
          >
            <h2>{editing ? "Editar usuario" : "Nuevo usuario"}</h2>

            <div className="form-row">
              <label>Nombre</label>
              <input
                className="input"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
              />
            </div>

            <div className="form-row">
              <label>Usuario de acceso</label>
              <input
                className="input"
                value={usuarioLogin}
                onChange={(e) => setUsuarioLogin(e.target.value)}
                disabled={!!editing}
              />
            </div>

            <div className="form-row">
              <label>{editing ? "Nueva contraseña (opcional)" : "Contraseña"}</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <div className="form-row">
              <label>Perfil base</label>
              <select
                className="input"
                value={rol}
                onChange={(e) => onChangeRol(e.target.value)}
                disabled={editing?.rol === "ADMIN"}
              >
                {perfiles.map((p) => (
                  <option key={p.codigo} value={p.codigo}>
                    {p.nombre}
                  </option>
                ))}
              </select>
              <p className="hint" style={{ marginTop: "0.35rem" }}>
                El perfil define permisos en la API. Los módulos controlan qué pantallas ve.
              </p>
            </div>

            {rol !== "ADMIN" && (
              <>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    marginBottom: "0.75rem",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={usarPersonalizado}
                    onChange={(e) => {
                      setUsarPersonalizado(e.target.checked);
                      if (!e.target.checked) {
                        setModulosSel(defaultsRol(rol));
                      }
                    }}
                  />
                  Personalizar módulos visibles
                </label>

                {usarPersonalizado && (
                  <div className="modulos-picker">
                    {[...modulosPorGrupo.entries()].map(([grupo, items]) => (
                      <div key={grupo} style={{ marginBottom: "0.75rem" }}>
                        <p className="hint" style={{ fontWeight: 600, marginBottom: "0.35rem" }}>
                          {grupo}
                        </p>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                          {items.map((m) => (
                            <label
                              key={m.path}
                              className={`extra-chip ${modulosSel.includes(m.path) ? "extra-chip--selected" : ""}`}
                              style={{ cursor: "pointer" }}
                            >
                              <input
                                type="checkbox"
                                checked={modulosSel.includes(m.path)}
                                onChange={() => toggleModulo(m.path)}
                                style={{ marginRight: "0.35rem" }}
                              />
                              {m.label}
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
              <button type="button" className="btn btn--accent" onClick={guardar}>
                Guardar
              </button>
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => setShowModal(false)}
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
