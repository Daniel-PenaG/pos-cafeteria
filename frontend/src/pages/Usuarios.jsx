import { useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import {
  getUsuarios,
  getPerfiles,
  createUsuario,
  updateUsuario,
  deleteUsuario,
} from "../services/usuariosService";

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState([]);
  const [perfiles, setPerfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);

  const [nombre, setNombre] = useState("");
  const [usuarioLogin, setUsuarioLogin] = useState("");
  const [password, setPassword] = useState("");
  const [rol, setRol] = useState("CAJERO");

  const cargar = async () => {
    setLoading(true);
    try {
      const [u, p] = await Promise.all([getUsuarios(), getPerfiles()]);
      setUsuarios(u);
      setPerfiles(p);
    } catch {
      alert("Error al cargar usuarios");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const abrirNuevo = () => {
    setEditing(null);
    setNombre("");
    setUsuarioLogin("");
    setPassword("");
    setRol("CAJERO");
    setShowModal(true);
  };

  const abrirEditar = (u) => {
    setEditing(u);
    setNombre(u.nombre);
    setUsuarioLogin(u.usuario_login);
    setPassword("");
    setRol(u.rol);
    setShowModal(true);
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

    try {
      if (editing) {
        const payload = { nombre, rol };
        if (password) payload.password = password;
        await updateUsuario(editing.id_usuario, payload);
      } else {
        await createUsuario({
          nombre,
          usuario_login: usuarioLogin,
          password,
          rol,
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
        subtitle="Solo el administrador gestiona cuentas y roles del sistema"
      >
        <button type="button" className="btn btn--accent" onClick={abrirNuevo}>
          + Nuevo usuario
        </button>
      </PageHeader>

      {loading ? (
        <p>Cargando…</p>
      ) : (
        <div className="card">
          <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Usuario</th>
                <th>Perfil</th>
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
        </div>
      )}

      <div className="card" style={{ marginTop: "1.5rem" }}>
        <h3>Perfiles disponibles</h3>
        <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.25rem" }}>
          <li>
            <strong>Administrador</strong> — acceso completo: catálogo, compras,
            reportes, promociones y configuración.
          </li>
          <li>
            <strong>Cajero</strong> — ventas, comandera y clientes (fidelidad).
          </li>
          <li>
            <strong>Cocina</strong> — solo pantalla de comandera.
          </li>
        </ul>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
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
              <label>Perfil</label>
              <select
                className="input"
                value={rol}
                onChange={(e) => setRol(e.target.value)}
              >
                {perfiles.map((p) => (
                  <option key={p.codigo} value={p.codigo}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            </div>

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
