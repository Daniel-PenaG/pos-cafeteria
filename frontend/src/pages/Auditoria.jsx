import { useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import api from "../api/axios";

export default function Auditoria() {
  const [items, setItems] = useState([]);
  const [accion, setAccion] = useState("");
  const [loading, setLoading] = useState(false);

  const cargar = async () => {
    setLoading(true);
    try {
      const params = {};
      if (accion.trim()) params.accion = accion.trim();
      const res = await api.get("/auditoria/", { params });
      setItems(res.data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
    // Carga inicial de la bitácora.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <PageHeader title="Auditoría" subtitle="Registro de acciones sensibles (solo consulta)" />
      <div className="card" style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem" }}>
        <input
          className="input"
          placeholder="Filtrar acción (COBRO, LOGIN_OK…)"
          value={accion}
          onChange={(e) => setAccion(e.target.value)}
        />
        <button type="button" className="btn btn--accent" onClick={cargar}>
          Buscar
        </button>
      </div>
      {loading ? (
        <p>Cargando…</p>
      ) : (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Acción</th>
                <th>Usuario</th>
                <th>Origen</th>
                <th>Entidad</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id_auditoria}>
                  <td>{i.fecha_hora}</td>
                  <td>{i.accion}</td>
                  <td>{i.id_usuario ?? i.usuario_login_intentado ?? "—"}</td>
                  <td>{i.origen || "—"}</td>
                  <td>
                    {i.entidad || "—"}
                    {i.entidad_id ? ` #${i.entidad_id}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
