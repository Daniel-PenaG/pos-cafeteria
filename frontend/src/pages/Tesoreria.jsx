import { useCallback, useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import { useAuthStore } from "../store/authStore";
import { hasAction, isAdmin } from "../config/permissions";
import { botonBloqueado, formatoMxn, validarTraspaso } from "../utils/tesoreriaUi";
import {
  activarTesoreria,
  crearAjuste,
  crearAportacion,
  crearComision,
  crearConciliacion,
  crearRetiro,
  crearTraspaso,
  getConciliaciones,
  getEstadoTesoreria,
  getMovimientosTesoreria,
  getResumenTesoreria,
  revertirOperacion,
} from "../services/tesoreriaService";

const CUENTAS = [
  { codigo: "EFECTIVO_CAFETERIA", nombre: "Efectivo en cafetería" },
  { codigo: "EFECTIVO_CASA", nombre: "Efectivo en casa" },
  { codigo: "BANCO", nombre: "Cuenta bancaria" },
];

function clave() {
  return crypto.randomUUID();
}

function mensajeError(err) {
  const detail = err?.response?.data?.detail;
  if (err?.response?.status === 403) return "No tienes permiso para esta operación";
  if (err?.response?.status === 409) {
    return typeof detail === "string" ? detail : "La operación ya fue registrada. No se duplicó.";
  }
  return typeof detail === "string" ? detail : "No se pudo completar la operación";
}

export default function Tesoreria() {
  const user = useAuthStore((s) => s.user);
  const admin = isAdmin(user?.rol);
  const puede = (codigo) => hasAction(user?.rol, codigo, user?.permisos_acciones);
  const [estado, setEstado] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [movimientos, setMovimientos] = useState([]);
  const [conciliaciones, setConciliaciones] = useState([]);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [modal, setModal] = useState(null);
  const [activacion, setActivacion] = useState({
    fecha_corte: new Date().toISOString().slice(0, 16),
    efectivo_cafeteria: "0",
    efectivo_casa: "0",
    saldo_banco: "0",
    observacion: "Saldo inicial sintético",
    confirmar: false,
  });
  const [form, setForm] = useState({
    codigo_origen: "EFECTIVO_CAFETERIA",
    codigo_destino: "EFECTIVO_CASA",
    codigo_cuenta: "BANCO",
    importe: "",
    concepto: "",
    observacion: "",
    saldo_fisico: "",
    tipo: "AJUSTE_FALTANTE",
    id_operacion: "",
    motivo: "",
  });

  const cargar = useCallback(async () => {
    const est = await getEstadoTesoreria();
    setEstado(est);
    if (!est.activa) {
      setResumen(null);
      setMovimientos([]);
      setConciliaciones([]);
      return;
    }
    const [res, movs, conc] = await Promise.all([
      getResumenTesoreria(),
      getMovimientosTesoreria({ limite: 30 }),
      getConciliaciones(),
    ]);
    setResumen(res);
    setMovimientos(movs.items || []);
    setConciliaciones(conc || []);
  }, []);

  useEffect(() => {
    cargar().catch((err) => setError(mensajeError(err)));
  }, [cargar]);

  async function enviar(accion) {
    if (enviando) return;
    setEnviando(true);
    setError("");
    try {
      await accion();
      setModal(null);
      await cargar();
    } catch (err) {
      if (err?.response?.status !== 401) setError(mensajeError(err));
    } finally {
      setEnviando(false);
    }
  }

  const saldoDe = (codigo) =>
    Number(resumen?.cuentas?.find((c) => c.codigo === codigo)?.saldo || 0);

  return (
    <div className="page tesoreria-page">
      <PageHeader title="Tesorería" subtitle="Efectivo en cafetería, en casa y cuenta bancaria" />
      {error && <p className="form-error">{error}</p>}
      {estado && !estado.activa && (
        <section className="card">
          <h2>Tesorería sin activar</h2>
          <p>Los cobros siguen igual. Aún no se generan movimientos ni se reconstruyen ventas anteriores.</p>
          {admin && puede("TESORERIA_ACTIVAR") && (
            <form
              className="tesoreria-grid"
              onSubmit={(e) => {
                e.preventDefault();
                enviar(() =>
                  activarTesoreria({
                    ...activacion,
                    fecha_corte: new Date(activacion.fecha_corte).toISOString(),
                    efectivo_cafeteria: Number(activacion.efectivo_cafeteria),
                    efectivo_casa: Number(activacion.efectivo_casa),
                    saldo_banco: Number(activacion.saldo_banco),
                    operation_id: clave(),
                  })
                );
              }}
            >
              <label>Fecha y hora de corte
                <input className="input" type="datetime-local" value={activacion.fecha_corte} onChange={(e) => setActivacion({ ...activacion, fecha_corte: e.target.value })} />
              </label>
              <label>Efectivo en cafetería
                <input className="input" inputMode="decimal" value={activacion.efectivo_cafeteria} onChange={(e) => setActivacion({ ...activacion, efectivo_cafeteria: e.target.value })} />
              </label>
              <label>Efectivo en casa
                <input className="input" inputMode="decimal" value={activacion.efectivo_casa} onChange={(e) => setActivacion({ ...activacion, efectivo_casa: e.target.value })} />
              </label>
              <label>Saldo bancario
                <input className="input" inputMode="decimal" value={activacion.saldo_banco} onChange={(e) => setActivacion({ ...activacion, saldo_banco: e.target.value })} />
              </label>
              <label>Observación
                <input className="input" value={activacion.observacion} onChange={(e) => setActivacion({ ...activacion, observacion: e.target.value })} />
              </label>
              <label className="tesoreria-check">
                <input type="checkbox" checked={activacion.confirmar} onChange={(e) => setActivacion({ ...activacion, confirmar: e.target.checked })} />
                Confirmo los saldos iniciales
              </label>
              <button className="btn btn--primary" type="submit" disabled={botonBloqueado(enviando) || !activacion.confirmar}>Activar tesorería</button>
            </form>
          )}
        </section>
      )}

      {resumen && (
        <>
          <section className="tesoreria-grid tesoreria-grid--cuentas">
            {resumen.cuentas.map((cuenta) => (
              <article key={cuenta.codigo} className="card">
                <h2>{cuenta.nombre}</h2>
                <p className="tesoreria-saldo">{formatoMxn(cuenta.saldo)}</p>
              </article>
            ))}
          </section>
          <section className="card">
            <p>Total disponible {formatoMxn(resumen.total_disponible)}</p>
            <p>Ingresos del periodo {formatoMxn(resumen.ingresos)}</p>
            <p>Gastos operativos {formatoMxn(resumen.gastos_operativos)}</p>
            <p>Comisiones {formatoMxn(resumen.comisiones)}</p>
            <p>Retiros del propietario {formatoMxn(resumen.retiros_propietario)}</p>
            <p>Diferencias pendientes {resumen.diferencias_pendientes}</p>
            <div className="tesoreria-acciones">
              {puede("TESORERIA_TRASPASAR") && <button className="btn btn--primary" type="button" onClick={() => setModal("traspaso")}>Nuevo traspaso</button>}
              {admin && <button className="btn" type="button" onClick={() => setModal("aportacion")}>Aportación</button>}
              {admin && <button className="btn" type="button" onClick={() => setModal("retiro")}>Retiro</button>}
              {puede("TESORERIA_REGISTRAR_GASTO") && <button className="btn" type="button" onClick={() => setModal("comision")}>Comisión bancaria</button>}
              {admin && <button className="btn" type="button" onClick={() => setModal("conciliacion")}>Conciliación</button>}
              {admin && <button className="btn" type="button" onClick={() => setModal("ajuste")}>Ajuste</button>}
              {admin && <button className="btn" type="button" onClick={() => setModal("reversa")}>Reversa</button>}
            </div>
          </section>
          <section className="card">
            <h2>Historial</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Fecha</th><th>Tipo</th><th>Cuenta</th><th>Dirección</th><th>Importe</th><th>Concepto</th>
                  </tr>
                </thead>
                <tbody>
                  {movimientos.map((mov) => (
                    <tr key={mov.id_movimiento}>
                      <td>{mov.fecha_operacion?.replace("T", " ").slice(0, 16)}</td>
                      <td>{mov.tipo}</td>
                      <td>{mov.codigo_cuenta}</td>
                      <td>{mov.direccion}</td>
                      <td>{formatoMxn(mov.importe)}</td>
                      <td>{mov.concepto}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card">
            <h2>Conciliaciones</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Cuenta</th><th>Sistema</th><th>Físico</th><th>Diferencia</th><th>Estado</th></tr>
                </thead>
                <tbody>
                  {conciliaciones.map((fila) => (
                    <tr key={fila.id_conciliacion}>
                      <td>{fila.codigo_cuenta}</td>
                      <td>{formatoMxn(fila.saldo_sistema)}</td>
                      <td>{formatoMxn(fila.saldo_fisico)}</td>
                      <td>{formatoMxn(fila.diferencia)}</td>
                      <td>{fila.estado}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {modal && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h2>{modal}</h2>
            {modal === "traspaso" && (
              <p className="hint">{validarTraspaso({
                origen: form.codigo_origen,
                destino: form.codigo_destino,
                importe: form.importe,
                disponible: saldoDe(form.codigo_origen),
              })}</p>
            )}
            {modal === "traspaso" && (
              <>
                <select className="select" aria-label="Cuenta origen" value={form.codigo_origen} onChange={(e) => setForm({ ...form, codigo_origen: e.target.value })}>
                  {CUENTAS.map((c) => <option key={c.codigo} value={c.codigo}>{c.nombre}</option>)}
                </select>
                <select className="select" aria-label="Cuenta destino" value={form.codigo_destino} onChange={(e) => setForm({ ...form, codigo_destino: e.target.value })}>
                  {CUENTAS.map((c) => <option key={c.codigo} value={c.codigo}>{c.nombre}</option>)}
                </select>
              </>
            )}
            {modal !== "traspaso" && modal !== "reversa" && (
              <select className="select" aria-label="Cuenta" value={form.codigo_cuenta} onChange={(e) => setForm({ ...form, codigo_cuenta: e.target.value })}>
                {CUENTAS.map((c) => <option key={c.codigo} value={c.codigo}>{c.nombre}</option>)}
              </select>
            )}
            {modal !== "reversa" && modal !== "conciliacion" && (
              <input className="input" placeholder="Importe" inputMode="decimal" value={form.importe} onChange={(e) => setForm({ ...form, importe: e.target.value })} />
            )}
            {modal === "conciliacion" && (
              <input className="input" placeholder="Saldo físico o bancario" inputMode="decimal" value={form.saldo_fisico} onChange={(e) => setForm({ ...form, saldo_fisico: e.target.value })} />
            )}
            {modal === "ajuste" && (
              <select className="select" aria-label="Tipo de ajuste" value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                <option value="AJUSTE_SOBRANTE">Sobrante</option>
                <option value="AJUSTE_FALTANTE">Faltante</option>
              </select>
            )}
            {modal === "reversa" ? (
              <>
                <input className="input" placeholder="Id de operación" value={form.id_operacion} onChange={(e) => setForm({ ...form, id_operacion: e.target.value })} />
                <input className="input" placeholder="Motivo" value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} />
              </>
            ) : (
              <>
                <input className="input" placeholder="Concepto" value={form.concepto} onChange={(e) => setForm({ ...form, concepto: e.target.value })} />
                <input className="input" placeholder="Observación" value={form.observacion} onChange={(e) => setForm({ ...form, observacion: e.target.value })} />
              </>
            )}
            <div className="modal-footer">
              <button className="btn" type="button" onClick={() => setModal(null)} disabled={botonBloqueado(enviando)}>Cancelar</button>
              <button
                className="btn btn--primary"
                type="button"
                disabled={botonBloqueado(enviando)}
                onClick={() => {
                  const aviso = modal === "traspaso"
                    ? validarTraspaso({
                      origen: form.codigo_origen,
                      destino: form.codigo_destino,
                      importe: form.importe,
                      disponible: saldoDe(form.codigo_origen),
                    })
                    : "";
                  if (aviso) {
                    setError(aviso);
                    return;
                  }
                  const base = {
                    importe: Number(form.importe),
                    concepto: form.concepto || modal,
                    observacion: form.observacion,
                    operation_id: clave(),
                  };
                  if (modal === "traspaso") {
                    enviar(() => crearTraspaso({ ...base, codigo_origen: form.codigo_origen, codigo_destino: form.codigo_destino }));
                  } else if (modal === "aportacion") {
                    enviar(() => crearAportacion({ ...base, codigo_cuenta: form.codigo_cuenta }));
                  } else if (modal === "retiro") {
                    enviar(() => crearRetiro({ ...base, codigo_cuenta: form.codigo_cuenta }));
                  } else if (modal === "comision") {
                    enviar(() => crearComision({ ...base, codigo_cuenta: "BANCO" }));
                  } else if (modal === "ajuste") {
                    enviar(() => crearAjuste({ ...base, codigo_cuenta: form.codigo_cuenta, tipo: form.tipo }));
                  } else if (modal === "conciliacion") {
                    enviar(() => crearConciliacion({
                      codigo_cuenta: form.codigo_cuenta,
                      saldo_fisico: Number(form.saldo_fisico),
                      observacion: form.observacion,
                    }));
                  } else if (modal === "reversa") {
                    enviar(() => revertirOperacion(form.id_operacion, { motivo: form.motivo, operation_id: clave() }));
                  }
                }}
              >
                {enviando ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
