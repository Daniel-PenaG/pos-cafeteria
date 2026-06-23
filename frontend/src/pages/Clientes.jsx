import { useEffect, useState } from "react";
import {
  getClientes,
  getCliente,
  createCliente,
  updateCliente,
  ajustarPuntos,
  getFidelidadConfig,
  updateFidelidadConfig,
  qrUrl,
} from "../services/clientesService";
import { useAuthStore } from "../store/authStore";
import PageHeader from "../components/PageHeader";

export default function Clientes() {
  const usuario = useAuthStore((s) => s.user);
  const [clientes, setClientes] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filtro, setFiltro] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [showDetalle, setShowDetalle] = useState(null);
  const [editing, setEditing] = useState(null);
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [pesosPorPunto, setPesosPorPunto] = useState("10");
  const [minimoCompra, setMinimoCompra] = useState("0");
  const [ajustePuntos, setAjustePuntos] = useState("");
  const [ajusteNotas, setAjusteNotas] = useState("");

  const load = async () => {
    try {
      setLoading(true);
      const [c, cfg] = await Promise.all([getClientes(), getFidelidadConfig()]);
      setClientes(c);
      setConfig(cfg);
      setPesosPorPunto(String(cfg.pesos_por_punto));
      setMinimoCompra(String(cfg.minimo_compra_acumular));
    } catch (err) {
      console.error(err);
      alert("Error al cargar clientes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const abrirNuevo = () => {
    setEditing(null);
    setNombre("");
    setTelefono("");
    setShowModal(true);
  };

  const abrirEditar = (c) => {
    setEditing(c);
    setNombre(c.nombre);
    setTelefono(c.telefono);
    setShowModal(true);
  };

  const abrirDetalle = async (id) => {
    try {
      const det = await getCliente(id);
      setShowDetalle(det);
      setAjustePuntos("");
      setAjusteNotas("");
    } catch (err) {
      alert(err.response?.data?.detail || "Error al cargar detalle");
    }
  };

  const guardarCliente = async () => {
    try {
      if (editing) {
        await updateCliente(editing.id_cliente, { nombre, telefono });
      } else {
        await createCliente({ nombre, telefono });
      }
      setShowModal(false);
      load();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al guardar");
    }
  };

  const guardarConfig = async () => {
    try {
      await updateFidelidadConfig({
        pesos_por_punto: Number(pesosPorPunto),
        minimo_compra_acumular: Number(minimoCompra),
      });
      alert("Configuración de fidelidad actualizada");
      load();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al guardar configuración");
    }
  };

  const enviarAjuste = async () => {
    if (!showDetalle || !usuario?.id_usuario) return;
    try {
      await ajustarPuntos(showDetalle.id_cliente, {
        puntos: Number(ajustePuntos),
        notas: ajusteNotas,
        id_usuario: usuario.id_usuario,
      });
      abrirDetalle(showDetalle.id_cliente);
      load();
      setAjustePuntos("");
      setAjusteNotas("");
    } catch (err) {
      alert(err.response?.data?.detail || "Error al ajustar puntos");
    }
  };

  const filtrados = clientes.filter((c) => {
    const t = filtro.toLowerCase();
    return (
      c.nombre.toLowerCase().includes(t) ||
      c.telefono.includes(t) ||
      c.codigo_fidelidad.toLowerCase().includes(t)
    );
  });

  return (
    <div className="page">
      <PageHeader
        title="Clientes y fidelidad"
        subtitle="Programa de puntos por monto gastado"
      >
        <button type="button" className="btn btn--primary" onClick={abrirNuevo}>
          + Nuevo cliente
        </button>
      </PageHeader>

      <section className="section card">
        <h2>Configuración de puntos</h2>
        <p className="hint">
          Regla: cada ${pesosPorPunto || "10"} MXN gastados = 1 punto
        </p>
        <div className="form-row" style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <label>Pesos por punto</label>
            <input
              className="input"
              type="number"
              min="1"
              step="0.01"
              value={pesosPorPunto}
              onChange={(e) => setPesosPorPunto(e.target.value)}
            />
          </div>
          <div>
            <label>Mínimo compra para acumular ($)</label>
            <input
              className="input"
              type="number"
              min="0"
              step="0.01"
              value={minimoCompra}
              onChange={(e) => setMinimoCompra(e.target.value)}
            />
          </div>
          <div style={{ alignSelf: "flex-end" }}>
            <button type="button" className="btn btn--secondary" onClick={guardarConfig}>
              Guardar reglas
            </button>
          </div>
        </div>
        {config && (
          <p className="hint" style={{ marginTop: "0.5rem" }}>
            Ejemplo: compra de $85 → {Math.floor(85 / Number(pesosPorPunto || 10))} pts
          </p>
        )}
      </section>

      <section className="section">
        <div className="form-row">
          <label>Buscar</label>
          <input
            className="input"
            placeholder="Nombre, teléfono o código CAFE-..."
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
          />
        </div>

        {loading ? (
          <p>Cargando…</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Teléfono</th>
                  <th>Código QR</th>
                  <th>Puntos</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filtrados.map((c) => (
                  <tr key={c.id_cliente}>
                    <td>{c.nombre}</td>
                    <td>{c.telefono}</td>
                    <td>
                      <code>{c.codigo_fidelidad}</code>
                    </td>
                    <td>
                      <strong>{c.puntos_saldo}</strong>
                    </td>
                    <td>{c.activo ? "Activo" : "Inactivo"}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--sm btn--secondary"
                        onClick={() => abrirDetalle(c.id_cliente)}
                      >
                        Ver
                      </button>{" "}
                      <button
                        type="button"
                        className="btn btn--sm btn--primary"
                        onClick={() => abrirEditar(c)}
                      >
                        Editar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h2>{editing ? "Editar cliente" : "Nuevo cliente"}</h2>
            <div className="form-row">
              <label>Nombre</label>
              <input
                className="input"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
              />
            </div>
            <div className="form-row">
              <label>Teléfono</label>
              <input
                className="input"
                value={telefono}
                onChange={(e) => setTelefono(e.target.value)}
                placeholder="10 dígitos mínimo"
              />
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn--secondary" onClick={() => setShowModal(false)}>
                Cancelar
              </button>
              <button type="button" className="btn btn--primary" onClick={guardarCliente}>
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}

      {showDetalle && (
        <div className="modal-overlay" onClick={() => setShowDetalle(null)}>
          <div className="modal-box modal-box--wide" onClick={(e) => e.stopPropagation()}>
            <h2>{showDetalle.nombre}</h2>
            <p>
              Tel: {showDetalle.telefono} · <strong>{showDetalle.puntos_saldo} pts</strong>
            </p>
            <div style={{ textAlign: "center", margin: "1rem 0" }}>
              <img
                src={qrUrl(showDetalle.codigo_fidelidad)}
                alt={`QR ${showDetalle.codigo_fidelidad}`}
                width={200}
                height={200}
              />
              <p>
                <code>{showDetalle.codigo_fidelidad}</code>
              </p>
            </div>

            <h3>Ajuste manual de puntos</h3>
            <div className="form-row" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <input
                className="input"
                type="number"
                placeholder="± puntos"
                value={ajustePuntos}
                onChange={(e) => setAjustePuntos(e.target.value)}
                style={{ width: 100 }}
              />
              <input
                className="input"
                placeholder="Motivo"
                value={ajusteNotas}
                onChange={(e) => setAjusteNotas(e.target.value)}
                style={{ flex: 1, minWidth: 160 }}
              />
              <button type="button" className="btn btn--secondary" onClick={enviarAjuste}>
                Aplicar
              </button>
            </div>

            <h3>Historial</h3>
            {showDetalle.movimientos?.length === 0 ? (
              <p className="hint">Sin movimientos aún</p>
            ) : (
              <ul className="mov-list">
                {showDetalle.movimientos?.map((m) => (
                  <li key={m.id_movimiento}>
                    <span className={m.puntos >= 0 ? "text-success" : "text-danger"}>
                      {m.puntos >= 0 ? "+" : ""}
                      {m.puntos} pts
                    </span>
                    {" · "}
                    {m.tipo} — saldo {m.saldo_despues}
                    {m.notas && ` — ${m.notas}`}
                    <br />
                    <small>{new Date(m.fecha_hora).toLocaleString()}</small>
                  </li>
                ))}
              </ul>
            )}

            <div className="modal-footer">
              <button type="button" className="btn btn--primary" onClick={() => setShowDetalle(null)}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
