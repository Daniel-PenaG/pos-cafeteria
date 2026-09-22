import { useCallback, useEffect, useMemo, useState } from "react";
import PageHeader from "../components/PageHeader";
import { useAuthStore } from "../store/authStore";
import {
  abrirCaja,
  cerrarCaja,
  getMiSesionCaja,
  getTerminalesCaja,
  iniciarArqueoCaja,
  registrarMovimientoCaja,
} from "../services/cajaService";
import { printTicketSafely } from "../services/printerService";
import { buildCierreCajaTicket } from "../services/escposTickets";
import { formatApiError } from "../utils/apiError";
import { createOperationId, isNetworkRetryError } from "../utils/operationId";
import { formatearHoraMexico } from "../utils/datetimeMx";
import {
  DENOMINACIONES_CAJA,
  cantidadesVacias,
  etiquetaEstadoCaja,
  fmtCaja,
  payloadDenominaciones,
  totalDesdeDenominaciones,
} from "../utils/cajaArqueo.js";
import { hasAction } from "../config/permissions";
import { HiOutlineBanknotes } from "react-icons/hi2";

const TIPOS_MOV = [
  { value: "ENTRADA", label: "Entrada" },
  { value: "RETIRO", label: "Retiro" },
  { value: "GASTO_CAJA", label: "Gasto desde caja" },
  { value: "DEVOLUCION", label: "Devolución" },
];

export default function CierreCaja() {
  const user = useAuthStore((s) => s.user);
  const [sesion, setSesion] = useState(null);
  const [cajaRequerida, setCajaRequerida] = useState(false);
  const [terminales, setTerminales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [avisoPrint, setAvisoPrint] = useState("");

  const [fondo, setFondo] = useState("");
  const [terminal, setTerminal] = useState("CAJA-1");
  const [obsApertura, setObsApertura] = useState("");
  const [openOpId, setOpenOpId] = useState(() => createOperationId());

  const [tipoMov, setTipoMov] = useState("ENTRADA");
  const [importeMov, setImporteMov] = useState("");
  const [motivoMov, setMotivoMov] = useState("");
  const [movOpId, setMovOpId] = useState(() => createOperationId());

  const [cantidades, setCantidades] = useState(cantidadesVacias);
  const [capturaDirecta, setCapturaDirecta] = useState(false);
  const [efectivoDirecto, setEfectivoDirecto] = useState("");
  const [declTrans, setDeclTrans] = useState("");
  const [declTerm, setDeclTerm] = useState("");
  const [refTerm, setRefTerm] = useState("");
  const [loteTerm, setLoteTerm] = useState("");
  const [refTrans, setRefTrans] = useState("");
  const [obsCierre, setObsCierre] = useState("");
  const [closeOpId, setCloseOpId] = useState(() => createOperationId());
  const [forzar, setForzar] = useState(false);

  const puedeAbrir = hasAction(user?.rol, "ABRIR_CAJA", user?.permisos_acciones);
  const puedeMover = hasAction(user?.rol, "REGISTRAR_MOVIMIENTO_CAJA", user?.permisos_acciones);
  const puedeCerrar = hasAction(user?.rol, "CERRAR_CAJA", user?.permisos_acciones);
  const puedeForzar = hasAction(user?.rol, "FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS", user?.permisos_acciones);

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const [mine, terms] = await Promise.all([getMiSesionCaja(), getTerminalesCaja()]);
      setSesion(mine.sesion || null);
      setCajaRequerida(Boolean(mine.caja_requerida));
      setTerminales(Array.isArray(terms) ? terms : []);
    } catch (err) {
      alert(formatApiError(err, "Error al cargar la caja"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const fisicoDenoms = useMemo(() => totalDesdeDenominaciones(cantidades), [cantidades]);
  const estado = sesion?.estado;
  const ciego = Boolean(sesion?.ciego) || estado === "EN_ARQUEO";
  const abierta = estado === "ABIERTA";
  const cerrada = ["CERRADA_CONCILIADA", "CERRADA_CON_DIFERENCIA", "REVISADA"].includes(estado);

  const handleAbrir = async () => {
    const fondoNum = Number(fondo);
    if (!Number.isFinite(fondoNum) || fondoNum < 0) {
      alert("Indica el fondo inicial");
      return;
    }
    try {
      setBusy(true);
      const data = await abrirCaja({
        fondo_inicial: fondoNum,
        terminal,
        observacion: obsApertura || null,
        operation_id: openOpId,
      });
      setSesion(data);
      setOpenOpId(createOperationId());
    } catch (err) {
      if (isNetworkRetryError(err)) {
        alert(formatApiError(err, "Reintenta; no se creó una segunda caja si el primer intento llegó"));
        return;
      }
      alert(formatApiError(err, "No se pudo abrir la caja"));
    } finally {
      setBusy(false);
    }
  };

  const handleMovimiento = async () => {
    const importe = Number(importeMov);
    if (!Number.isFinite(importe) || importe <= 0) {
      alert("El importe debe ser mayor a cero");
      return;
    }
    if (!motivoMov.trim()) {
      alert("Indica el motivo");
      return;
    }
    try {
      setBusy(true);
      await registrarMovimientoCaja({
        tipo: tipoMov,
        importe,
        motivo: motivoMov.trim(),
        metodo: "EFECTIVO",
        operation_id: movOpId,
      });
      setImporteMov("");
      setMotivoMov("");
      setMovOpId(createOperationId());
      await cargar();
    } catch (err) {
      alert(formatApiError(err, "No se pudo registrar el movimiento"));
    } finally {
      setBusy(false);
    }
  };

  const handleIniciarArqueo = async () => {
    try {
      setBusy(true);
      const data = await iniciarArqueoCaja();
      setSesion(data);
      setCantidades(cantidadesVacias());
      setCloseOpId(createOperationId());
    } catch (err) {
      alert(formatApiError(err, "No se pudo iniciar el arqueo"));
    } finally {
      setBusy(false);
    }
  };

  const handleCerrar = async () => {
    const trans = Number(declTrans);
    const term = Number(declTerm);
    if (!Number.isFinite(trans) || trans < 0 || !Number.isFinite(term) || term < 0) {
      alert("Indica transferencia y terminal declaradas");
      return;
    }
    const payload = {
      denominaciones: capturaDirecta ? [] : payloadDenominaciones(cantidades),
      declarado_efectivo: capturaDirecta ? Number(efectivoDirecto) : null,
      declarado_transferencia: trans,
      declarado_tarjeta: term,
      captura_directa: capturaDirecta,
      ref_terminal: refTerm || null,
      lote_terminal: loteTerm || null,
      ref_transferencia: refTrans || null,
      observacion: obsCierre || null,
      forzar,
      operation_id: closeOpId,
    };
    if (capturaDirecta && (!Number.isFinite(payload.declarado_efectivo) || payload.declarado_efectivo < 0)) {
      alert("Indica el efectivo contado");
      return;
    }
    try {
      setBusy(true);
      const data = await cerrarCaja(payload);
      setSesion(data);
      setAvisoPrint("");
    } catch (err) {
      alert(formatApiError(err, "No se pudo cerrar la caja"));
    } finally {
      setBusy(false);
    }
  };

  const handleImprimir = async () => {
    const printResult = await printTicketSafely(buildCierreCajaTicket, { sesion, usuario: user });
    if (!printResult.ok) {
      setAvisoPrint(printResult.message || "La impresión falló. El cierre ya quedó registrado.");
    } else if (printResult.skipped) {
      setAvisoPrint("Impresión no disponible en este dispositivo. El cierre ya quedó registrado.");
    } else {
      setAvisoPrint("Resumen enviado a la impresora.");
    }
  };

  if (loading) return <div className="loading-state">Cargando…</div>;

  return (
    <div className="caja-page">
      <PageHeader
        title="Caja"
        subtitle="Apertura, movimientos, arqueo ciego y conciliación por turno"
      />

      {cajaRequerida && !sesion && (
        <p className="hint caja-banner">Debes abrir caja antes de cobrar.</p>
      )}

      {!sesion && (
        <div className="card caja-card">
          <h3 className="inline-flex items-center gap-2">
            <HiOutlineBanknotes className="size-5 text-olive" aria-hidden />
            Abrir caja
          </h3>
          <div className="caja-form-grid">
            <div className="form-row">
              <label htmlFor="fondo-inicial">Fondo inicial *</label>
              <input
                id="fondo-inicial"
                type="number"
                min="0"
                step="0.01"
                className="input"
                value={fondo}
                onChange={(e) => setFondo(e.target.value)}
                inputMode="decimal"
              />
            </div>
            <div className="form-row">
              <label htmlFor="terminal-caja">Terminal / caja *</label>
              <select
                id="terminal-caja"
                className="select"
                value={terminal}
                onChange={(e) => setTerminal(e.target.value)}
              >
                {(terminales.length ? terminales : [{ codigo: "CAJA-1" }]).map((t) => (
                  <option key={t.codigo} value={t.codigo}>
                    {t.codigo}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-row">
            <label htmlFor="obs-apertura">Observación (opcional)</label>
            <textarea
              id="obs-apertura"
              className="input"
              rows={2}
              value={obsApertura}
              onChange={(e) => setObsApertura(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn btn--accent"
            onClick={handleAbrir}
            disabled={busy || !puedeAbrir}
          >
            {busy ? "Abriendo…" : "Abrir caja"}
          </button>
          {!puedeAbrir && <p className="hint">No tienes permiso para abrir caja.</p>}
        </div>
      )}

      {abierta && sesion && (
        <>
          <div className="grid-stats caja-stats">
            <div className="stat-card">
              <p className="stat-card__label">Apertura</p>
              <p className="stat-card__value">{formatearHoraMexico(sesion.fecha_apertura)}</p>
              <p className="hint">{sesion.terminal}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Fondo inicial</p>
              <p className="stat-card__value">{fmtCaja(sesion.fondo_inicial)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Efectivo esperado</p>
              <p className="stat-card__value">{fmtCaja(sesion.efectivo_esperado)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Ventas</p>
              <p className="stat-card__value">{fmtCaja(sesion.ventas_total)}</p>
              <p className="hint">{sesion.num_ventas ?? 0} tickets</p>
            </div>
          </div>
          <div className="grid-stats caja-stats">
            <div className="stat-card">
              <p className="stat-card__label">Efectivo</p>
              <p className="stat-card__value">{fmtCaja(sesion.ventas_efectivo)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Transferencia</p>
              <p className="stat-card__value">{fmtCaja(sesion.ventas_transferencia)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Terminal</p>
              <p className="stat-card__value">{fmtCaja(sesion.ventas_tarjeta)}</p>
            </div>
            <div className="stat-card">
              <p className="stat-card__label">Entradas / retiros / gastos</p>
              <p className="stat-card__value">
                {fmtCaja(sesion.entradas)} / {fmtCaja(sesion.retiros)} / {fmtCaja(sesion.gastos_caja)}
              </p>
            </div>
          </div>

          {sesion.pedidos_abiertos?.length > 0 && (
            <div className="card caja-card">
              <h3>Pedidos abiertos</h3>
              <ul className="caja-list">
                {sesion.pedidos_abiertos.map((p) => (
                  <li key={p.id_pedido}>
                    Mesa {p.numero_mesa}
                    {p.para_llevar ? " · para llevar" : ""} · #{p.id_pedido}
                  </li>
                ))}
              </ul>
              <p className="hint">Ciérralos antes del cierre normal. Forzar no cobra ni cancela.</p>
            </div>
          )}

          {puedeMover && (
            <div className="card caja-card">
              <h3>Registrar movimiento</h3>
              <div className="caja-form-grid">
                <div className="form-row">
                  <label htmlFor="tipo-mov">Tipo</label>
                  <select id="tipo-mov" className="select" value={tipoMov} onChange={(e) => setTipoMov(e.target.value)}>
                    {TIPOS_MOV.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-row">
                  <label htmlFor="importe-mov">Importe *</label>
                  <input
                    id="importe-mov"
                    type="number"
                    min="0.01"
                    step="0.01"
                    className="input"
                    value={importeMov}
                    onChange={(e) => setImporteMov(e.target.value)}
                    inputMode="decimal"
                  />
                </div>
              </div>
              <div className="form-row">
                <label htmlFor="motivo-mov">Motivo *</label>
                <input
                  id="motivo-mov"
                  className="input"
                  value={motivoMov}
                  onChange={(e) => setMotivoMov(e.target.value)}
                />
              </div>
              <button type="button" className="btn btn--secondary" onClick={handleMovimiento} disabled={busy}>
                Registrar movimiento
              </button>
            </div>
          )}

          <div className="card caja-card">
            <h3>Iniciar cierre</h3>
            <p className="hint">El arqueo es ciego: primero capturas lo encontrado, luego se muestran los esperados.</p>
            <button type="button" className="btn btn--accent" onClick={handleIniciarArqueo} disabled={busy || !puedeCerrar}>
              Iniciar arqueo
            </button>
          </div>
        </>
      )}

      {ciego && estado === "EN_ARQUEO" && (
        <div className="card caja-card">
          <h3>Arqueo ciego</h3>
          <p className="hint">Cuenta lo que hay en caja. Los totales esperados se muestran después de confirmar.</p>
          <label className="caja-check">
            <input
              type="checkbox"
              checked={capturaDirecta}
              onChange={(e) => setCapturaDirecta(e.target.checked)}
            />
            Captura directa del total (compatibilidad)
          </label>
          {capturaDirecta ? (
            <div className="form-row">
              <label htmlFor="efectivo-directo">Efectivo contado *</label>
              <input
                id="efectivo-directo"
                type="number"
                min="0"
                step="0.01"
                className="input"
                value={efectivoDirecto}
                onChange={(e) => setEfectivoDirecto(e.target.value)}
                inputMode="decimal"
              />
            </div>
          ) : (
            <>
              {["Billetes", "Monedas"].map((grupo) => (
                <div key={grupo} className="caja-denom-block">
                  <h4>{grupo}</h4>
                  <div className="caja-denom-grid">
                    {DENOMINACIONES_CAJA.filter((d) => d.grupo === grupo).map((d) => (
                      <label key={d.codigo} className="caja-denom">
                        <span>{d.label}</span>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          className="input"
                          value={cantidades[d.codigo]}
                          onChange={(e) =>
                            setCantidades((prev) => ({ ...prev, [d.codigo]: e.target.value }))
                          }
                          inputMode="numeric"
                        />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
              <p className="hint">Físico calculado (solo referencia): {fmtCaja(fisicoDenoms)}</p>
            </>
          )}
          <div className="caja-form-grid">
            <div className="form-row">
              <label htmlFor="decl-trans">Transferencia declarada *</label>
              <input
                id="decl-trans"
                type="number"
                min="0"
                step="0.01"
                className="input"
                value={declTrans}
                onChange={(e) => setDeclTrans(e.target.value)}
                inputMode="decimal"
              />
            </div>
            <div className="form-row">
              <label htmlFor="decl-term">Terminal declarada *</label>
              <input
                id="decl-term"
                type="number"
                min="0"
                step="0.01"
                className="input"
                value={declTerm}
                onChange={(e) => setDeclTerm(e.target.value)}
                inputMode="decimal"
              />
            </div>
          </div>
          <div className="caja-form-grid">
            <div className="form-row">
              <label htmlFor="ref-trans">Referencia transferencia</label>
              <input id="ref-trans" className="input" value={refTrans} onChange={(e) => setRefTrans(e.target.value)} />
            </div>
            <div className="form-row">
              <label htmlFor="ref-term">Corte / lote terminal</label>
              <input id="ref-term" className="input" value={refTerm} onChange={(e) => setRefTerm(e.target.value)} />
            </div>
            <div className="form-row">
              <label htmlFor="lote-term">Lote terminal</label>
              <input id="lote-term" className="input" value={loteTerm} onChange={(e) => setLoteTerm(e.target.value)} />
            </div>
          </div>
          <div className="form-row">
            <label htmlFor="obs-cierre">Observación (obligatoria si hay diferencia)</label>
            <textarea
              id="obs-cierre"
              className="input"
              rows={2}
              value={obsCierre}
              onChange={(e) => setObsCierre(e.target.value)}
            />
          </div>
          {puedeForzar && sesion.pedidos_abiertos?.length > 0 && (
            <label className="caja-check">
              <input type="checkbox" checked={forzar} onChange={(e) => setForzar(e.target.checked)} />
              Forzar cierre con pedidos abiertos
            </label>
          )}
          <button type="button" className="btn btn--accent" onClick={handleCerrar} disabled={busy || !puedeCerrar}>
            {busy ? "Cerrando…" : "Confirmar arqueo y cerrar"}
          </button>
        </div>
      )}

      {cerrada && sesion && (
        <ResultadoCaja sesion={sesion} onPrint={handleImprimir} avisoPrint={avisoPrint} />
      )}

      {sesion?.movimientos?.length > 0 && (
        <div className="card caja-card">
          <h3>Movimientos</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Importe</th>
                  <th>Motivo</th>
                  <th>Hora</th>
                </tr>
              </thead>
              <tbody>
                {sesion.movimientos.map((m) => (
                  <tr key={m.id_movimiento}>
                    <td>{m.tipo}</td>
                    <td>{fmtCaja(m.importe)}</td>
                    <td>{m.motivo}</td>
                    <td>{formatearHoraMexico(m.fecha_hora)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function ResultadoCaja({ sesion, onPrint, avisoPrint }) {
  const filas = [
    ["Efectivo", sesion.esperado_efectivo, sesion.declarado_efectivo, sesion.diferencia_efectivo],
    ["Transferencia", sesion.esperado_transferencia, sesion.declarado_transferencia, sesion.diferencia_transferencia],
    ["Terminal", sesion.esperado_tarjeta, sesion.declarado_tarjeta, sesion.diferencia_tarjeta],
  ];
  return (
    <div className="card caja-card">
      <h3>Conciliación</h3>
      <p className="hint">
        Estado: <strong>{etiquetaEstadoCaja(sesion.estado)}</strong>
        {sesion.forzado ? " · forzado" : ""} · turno {sesion.duracion_minutos ?? 0} min
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Método</th>
              <th>Esperado</th>
              <th>Declarado</th>
              <th>Diferencia</th>
            </tr>
          </thead>
          <tbody>
            {filas.map(([metodo, exp, dec, dif]) => (
              <tr key={metodo}>
                <td>{metodo}</td>
                <td>{fmtCaja(exp)}</td>
                <td>{fmtCaja(dec)}</td>
                <td>{fmtCaja(dif)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="caja-list">
        <li>Ventas totales: {fmtCaja(sesion.ventas_total)} ({sesion.num_ventas ?? 0})</li>
        <li>Ingreso monetario: {fmtCaja(sesion.ingreso_monetario)}</li>
        <li>Fondo: {fmtCaja(sesion.fondo_inicial)}</li>
        <li>Entradas: {fmtCaja(sesion.entradas)} · Retiros: {fmtCaja(sesion.retiros)}</li>
        <li>Gastos de caja: {fmtCaja(sesion.gastos_caja)} · Devoluciones: {fmtCaja(sesion.devoluciones)}</li>
        <li>
          Apertura {formatearHoraMexico(sesion.fecha_apertura)} · Cierre{" "}
          {formatearHoraMexico(sesion.fecha_cierre)}
        </li>
      </ul>
      {sesion.observacion_cierre && <p className="hint">Obs.: {sesion.observacion_cierre}</p>}
      <button type="button" className="btn btn--secondary" onClick={onPrint}>
        Imprimir resumen
      </button>
      {avisoPrint && <p className="hint">{avisoPrint}</p>}
    </div>
  );
}
