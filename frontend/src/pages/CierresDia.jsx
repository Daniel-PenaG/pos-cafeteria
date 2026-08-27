import { useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import { getCierresDia } from "../services/cierresService";
import { fechaMexicoISO, formatearHoraMexico } from "../utils/datetimeMx";
import { formatApiError } from "../utils/apiError";

function fmt(n) {
  return `$${Number(n).toFixed(2)}`;
}

export default function CierresDia() {
  const [fecha, setFecha] = useState(fechaMexicoISO());
  const [cierres, setCierres] = useState([]);
  const [loading, setLoading] = useState(true);

  const cargar = async () => {
    setLoading(true);
    try {
      const data = await getCierresDia(fecha);
      setCierres(data);
    } catch (err) {
      alert(formatApiError(err, "Error al cargar cierres"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
  }, [fecha]);

  const totalVentas = cierres.reduce((a, c) => a + Number(c.total_ventas), 0);
  const totalDiff = cierres.reduce((a, c) => a + Number(c.diferencia), 0);

  return (
    <div>
      <PageHeader
        title="Cierres del día"
        subtitle="Registro de arqueos por usuario (administración)"
      />

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="form-row" style={{ maxWidth: 220 }}>
          <label htmlFor="fecha-cierres">Fecha</label>
          <input
            id="fecha-cierres"
            type="date"
            className="input"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
          />
        </div>
      </div>

      {loading ? (
        <p>Cargando…</p>
      ) : cierres.length === 0 ? (
        <p className="empty-state">Nadie ha registrado cierre en esta fecha.</p>
      ) : (
        <>
          <div className="grid-stats" style={{ marginBottom: "1rem" }}>
            <div className="stat-card">
              <p className="stat-card__label">Cierres registrados</p>
              <p className="stat-card__value">{cierres.length}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Total ventas cerradas</p>
              <p className="stat-card__value">{fmt(totalVentas)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Diferencia acumulada</p>
              <p className="stat-card__value">{fmt(totalDiff)}</p>
            </div>
          </div>

          <div className="table-wrap card">
            <table>
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Hora cierre</th>
                  <th>Ventas</th>
                  <th>Total</th>
                  <th>Efectivo sistema</th>
                  <th>Contado</th>
                  <th>Diferencia</th>
                  <th>Notas</th>
                </tr>
              </thead>
              <tbody>
                {cierres.map((c) => (
                  <tr key={c.id_cierre}>
                    <td>
                      {c.nombre_usuario}
                      <span className="hint"> @{c.usuario_login}</span>
                    </td>
                    <td>{formatearHoraMexico(c.fecha_hora_registro)}</td>
                    <td>{c.num_ventas}</td>
                    <td>{fmt(c.total_ventas)}</td>
                    <td>{fmt(c.total_efectivo)}</td>
                    <td>{fmt(c.efectivo_contado)}</td>
                    <td
                      style={{
                        color: Number(c.diferencia) === 0 ? "inherit" : "var(--berry)",
                        fontWeight: 600,
                      }}
                    >
                      {fmt(c.diferencia)}
                    </td>
                    <td>{c.notas || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
