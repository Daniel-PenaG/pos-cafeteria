import { useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import { getResumenCierre, registrarCierre } from "../services/cierresService";
import { fechaMexicoISO, formatearHoraMexico } from "../utils/datetimeMx";
import { numberInputFromApi } from "../utils/numberInput";
import { HiOutlineBanknotes } from "react-icons/hi2";

function fmt(n) {
  return `$${Number(n).toFixed(2)}`;
}

export default function CierreCaja() {
  const [fecha, setFecha] = useState(fechaMexicoISO());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [efectivoContado, setEfectivoContado] = useState("");
  const [notas, setNotas] = useState("");
  const [guardando, setGuardando] = useState(false);

  const cargar = async () => {
    setLoading(true);
    try {
      const res = await getResumenCierre(fecha);
      setData(res);
      if (res.cierre) {
        setEfectivoContado(numberInputFromApi(res.cierre.efectivo_contado));
        setNotas(res.cierre.notas || "");
      } else {
        setEfectivoContado(numberInputFromApi(res.total_efectivo));
        setNotas("");
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Error al cargar resumen");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
  }, [fecha]);

  const contadoNum = parseFloat(efectivoContado);
  const diferencia =
    data && efectivoContado !== "" && !isNaN(contadoNum)
      ? Math.round((contadoNum - data.total_efectivo) * 100) / 100
      : null;

  const handleCierre = async () => {
    if (data?.ya_cerrado) {
      alert("Ya registraste el cierre de este día.");
      return;
    }
    if (efectivoContado === "" || isNaN(contadoNum) || contadoNum < 0) {
      alert("Indica el efectivo contado en caja");
      return;
    }
    if (!window.confirm("¿Confirmar cierre de caja del día?")) return;
    try {
      setGuardando(true);
      await registrarCierre(contadoNum, notas);
      alert("Cierre de caja registrado correctamente");
      cargar();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al registrar cierre");
    } finally {
      setGuardando(false);
    }
  };

  if (loading) return <div className="loading-state">Cargando…</div>;

  return (
    <div>
      <PageHeader
        title="Cierre de caja"
        subtitle="Registra tu arqueo al final del turno (hora México)"
      />

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="form-row" style={{ maxWidth: 220 }}>
          <label htmlFor="fecha-cierre">Fecha</label>
          <input
            id="fecha-cierre"
            type="date"
            className="input"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
          />
        </div>
      </div>

      {data && (
        <>
          <div className="grid-stats" style={{ marginBottom: "1rem" }}>
            <div className="stat-card">
              <p className="stat-card__label">Ventas cobradas</p>
              <p className="stat-card__value">{data.num_ventas}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Total del día</p>
              <p className="stat-card__value">{fmt(data.total_ventas)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Efectivo (sistema)</p>
              <p className="stat-card__value">{fmt(data.total_efectivo)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Tarjeta</p>
              <p className="stat-card__value">{fmt(data.total_tarjeta)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Transferencia</p>
              <p className="stat-card__value">{fmt(data.total_transferencia)}</p>
            </div>
          </div>

          {data.ya_cerrado ? (
            <div className="card" style={{ borderColor: "var(--olive-light)" }}>
              <h3>Cierre registrado</h3>
              <p className="hint">
                {formatearHoraMexico(data.cierre.fecha_hora_registro)} — Efectivo contado:{" "}
                <strong>{fmt(data.cierre.efectivo_contado)}</strong> · Diferencia:{" "}
                <strong>{fmt(data.cierre.diferencia)}</strong>
              </p>
              {data.cierre.notas && <p className="hint">Notas: {data.cierre.notas}</p>}
            </div>
          ) : (
            <div className="card">
              <h3 className="inline-flex items-center gap-2">
                <HiOutlineBanknotes className="size-5 text-olive" aria-hidden />
                Arqueo de efectivo
              </h3>
              <p className="hint">
                Cuenta el efectivo en caja e ingresa el total. El sistema compara con{" "}
                {fmt(data.total_efectivo)} en ventas en efectivo.
              </p>
              <div className="form-row" style={{ maxWidth: 280 }}>
                <label>Efectivo contado *</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="input"
                  value={efectivoContado}
                  onChange={(e) => setEfectivoContado(e.target.value)}
                />
              </div>
              {diferencia !== null && (
                <p className="hint" style={{ marginTop: "0.5rem" }}>
                  Diferencia:{" "}
                  <strong style={{ color: diferencia === 0 ? "var(--olive)" : "var(--berry)" }}>
                    {diferencia >= 0 ? "+" : ""}
                    {fmt(diferencia)}
                  </strong>
                  {diferencia > 0 ? " (sobrante)" : diferencia < 0 ? " (faltante)" : " (cuadra)"}
                </p>
              )}
              <div className="form-row">
                <label>Notas (opcional)</label>
                <textarea
                  className="input"
                  rows={2}
                  value={notas}
                  onChange={(e) => setNotas(e.target.value)}
                  placeholder="Ej. cambio inicial, retiro parcial…"
                />
              </div>
              <button
                type="button"
                className="btn btn--accent"
                onClick={handleCierre}
                disabled={guardando}
              >
                {guardando ? "Guardando…" : "Confirmar cierre de caja"}
              </button>
            </div>
          )}

          <div className="card" style={{ marginTop: "1rem" }}>
            <h3>Detalle de ventas</h3>
            {data.ventas.length === 0 ? (
              <p className="empty-state">Sin ventas en esta fecha.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Folio</th>
                      <th>Hora</th>
                      <th>Forma pago</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.ventas.map((v) => (
                      <tr key={v.id_venta}>
                        <td>#{v.id_venta}</td>
                        <td>{formatearHoraMexico(v.fecha_hora)}</td>
                        <td>{v.forma_pago}</td>
                        <td>{fmt(v.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
