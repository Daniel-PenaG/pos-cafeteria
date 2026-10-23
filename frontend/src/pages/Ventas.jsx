import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import {
  getCachedProductoContexto,
  getProductoContexto,
} from "../services/productoContextoService";
import { schedulePrefetchProductoContextos } from "../services/productoContextoPrefetch";
import {
  getPedidoMesa,
  agregarMesa,
  quitarMesa,
  agregarLineaPedido,
  agregarComboPedido,
  actualizarLineaPedido,
  eliminarLineaPedido,
  cobrarPedido,
  confirmarComandaPedido,
} from "../services/pedidosService";
import {
  calcularPromocion,
} from "../services/promocionesService";
import { OPCION_PRECIO_NORMAL, importeLinea, sumaImportes, textoPrecioLinea } from "../utils/promoCantidad";
import {
  buscarClientes,
  getCliente,
  getClientePorCodigo,
  createCliente,
  previewPuntos,
} from "../services/clientesService";
import { useAuthStore } from "../store/authStore";
import { isAdmin, canCancelarProductoEnComanda } from "../config/permissions";
import PageHeader from "../components/PageHeader";
import CancelacionLineaModal from "../components/CancelacionLineaModal";
import QrCodeDisplay from "../components/QrCodeDisplay";
import QrScannerModal from "../components/QrScannerModal";
import { parseCodigoFidelidad } from "../utils/fidelidadQr";
import SearchField from "../components/SearchField";
import ElapsedTimer from "../components/ElapsedTimer";
import PrinterSettings from "../components/PrinterSettings";
import { canUseBluetoothPrinter, printTicketSafely } from "../services/printerService";
import { buildCobroTicket, buildPrecuentaTicket } from "../services/escposTickets";
import { FORMAS_PAGO, esEfectivo } from "../utils/formaPago";
import {
  botonCobroBloqueado,
  cambioEfectivo,
  clientePrecargado,
  evaluarCanjeCliente,
  ocultaMetodoMonetario,
  payloadCobro,
  resolverErrorCobro,
} from "../utils/puntosPago";
import { getSavedPrinter } from "../services/printerStorage";
function segundosEnMesa(fechaApertura) {
  const segundos = Math.floor(
    (Date.now() - new Date(fechaApertura).getTime()) / 1000
  );
  return segundos >= 0 ? segundos : null;
}
import {
  HiOutlineShoppingCart,
  HiOutlineCheckBadge,
  HiOutlineBanknotes,
  HiOutlineShoppingBag,
  HiOutlineTableCells,
  HiOutlinePrinter,
  HiOutlinePlus,
  HiOutlineXMark,
  HiOutlineQrCode,
  HiOutlinePencilSquare,
} from "react-icons/hi2";
import {
  createIntentStore,
  createProductAddLock,
  fingerprintCombo,
  fingerprintLinea,
  shouldKeepPendingKey,
  withIntentRetry,
} from "../utils/operationIntent";
import { puedeAgregarRapido } from "../utils/agregadoRapido";
import { formatApiError } from "../utils/apiError";
import {
  accionQuitarLinea,
  debeRefrescarPedidoPorConflicto,
  esLineaCancelada,
  lineasActivas,
  requiereCancelacionEnviada,
} from "../utils/lineaPedidoAccion";
import { mergeMesaActivaFromPedido } from "../utils/ventasOperacionSync";
import { aplicarAgregadoOptimista } from "../utils/ventasOptimisticAdd";
import { bootstrapVentasShell } from "../services/ventasBootstrap";
import {
  fetchMesasActivasCached,
  invalidateMesasActivas,
} from "../cache/operationalCaches";
import { readVentasSession, writeVentasSession } from "../store/ventasNavStore";
import { toastError, toastInfo, toastSuccess } from "../store/toastStore";
import { showCobroExitoResumen } from "../store/cobroExitoStore";
import OperationalConfirmModal from "../components/OperationalConfirmModal";

const MESA_PARA_LLEVAR = 99;

function sumExtras(extras) {
  return extras.reduce((acc, e) => acc + Number(e.precio), 0);
}

function PrecioPromoLinea({ calc }) {
  const aplicaciones = Number(calc.aplicaciones || 0);
  const originales = Number(calc.precio_original_unitario || 0);
  return (
    <>
      <p style={{ margin: 0 }}>{textoPrecioLinea(calc)}</p>
      {aplicaciones > 0 && originales > 0 && (
        <p className="hint" style={{ margin: "0.25rem 0 0" }}>
          <s>${originales.toFixed(2)}</s> precio normal
        </p>
      )}
    </>
  );
}

export default function Ventas({ modoParaLlevar = false }) {
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [busquedaProducto, setBusquedaProducto] = useState("");
  const [categoriasAbiertas, setCategoriasAbiertas] = useState({});
  const [extrasModal, setExtrasModal] = useState([]);
  const [cargandoExtras, setCargandoExtras] = useState(false);
  const [pedido, setPedido] = useState(null);
  const [mesasActivas, setMesasActivas] = useState({});
  const [mesasLista, setMesasLista] = useState([]);
  const [editandoMesas, setEditandoMesas] = useState(false);
  const [gestionMesasLoading, setGestionMesasLoading] = useState(false);
  const [numeroMesa, setNumeroMesa] = useState(null);
  const [formaPago, setFormaPago] = useState("EFECTIVO");
  const [montoRecibido, setMontoRecibido] = useState("");
  const [loading, setLoading] = useState(false);
  const [guardandoLinea, setGuardandoLinea] = useState(false);

  const [productoModal, setProductoModal] = useState(null);
  const [extrasSeleccionados, setExtrasSeleccionados] = useState([]);
  const [promosDisponibles, setPromosDisponibles] = useState([]);
  const [promoModo, setPromoModo] = useState("auto");
  const [calculoPromo, setCalculoPromo] = useState(null);
  const [cantidadModal, setCantidadModal] = useState("");
  const [comentarioModal, setComentarioModal] = useState("");
  const [tiposPosLabels, setTiposPosLabels] = useState({});

  const [showCobroModal, setShowCobroModal] = useState(false);
  const [showImprimirTicketModal, setShowImprimirTicketModal] = useState(false);
  const [cobroPendiente, setCobroPendiente] = useState(null);
  const [clienteCobro, setClienteCobro] = useState(null);
  const [busquedaCobro, setBusquedaCobro] = useState("");
  const [resultadosCobro, setResultadosCobro] = useState([]);
  const [buscandoCobro, setBuscandoCobro] = useState(false);
  const [showNuevoCliente, setShowNuevoCliente] = useState(false);
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [nuevoTelefono, setNuevoTelefono] = useState("");
  const [puntosPreviewCobro, setPuntosPreviewCobro] = useState(0);
  const [puntosCanjeInput, setPuntosCanjeInput] = useState("");
  const [qrCobro, setQrCobro] = useState("");
  const [showQrScanner, setShowQrScanner] = useState(false);
  const [clienteQrRecienCreado, setClienteQrRecienCreado] = useState(null);
  const [showPrinterSettings, setShowPrinterSettings] = useState(false);
  const [imprimiendoPrecuenta, setImprimiendoPrecuenta] = useState(false);
  const [precuentaImpresa, setPrecuentaImpresa] = useState(false);
  /** Cantidades en edición (id detalle → texto) antes de guardar en servidor */
  const [cantidadEdit, setCantidadEdit] = useState({});

  const [promoConfirm, setPromoConfirm] = useState(null);
  const [calculoInicialModal, setCalculoInicialModal] = useState(null);
  const [revalidandoShell, setRevalidandoShell] = useState(false);
  useEffect(() => {
    if (import.meta.env.MODE !== "e2e") return undefined;
    const onSwrProbe = () => setRevalidandoShell(true);
    window.addEventListener("pos:e2e-catalog-swr-probe", onSwrProbe);
    return () => window.removeEventListener("pos:e2e-catalog-swr-probe", onSwrProbe);
  }, []);
  const [recalculoConfirm, setRecalculoConfirm] = useState(null);
  const [operConfirm, setOperConfirm] = useState(null);

  const askOperConfirm = useCallback(
    (options) =>
      new Promise((resolve) => {
        setOperConfirm({
          title: options.title || "Confirmar",
          message: options.message,
          confirmLabel: options.confirmLabel || "Continuar",
          cancelLabel: options.cancelLabel || "Cancelar",
          onConfirm: () => {
            setOperConfirm(null);
            resolve(true);
          },
          onCancel: () => {
            setOperConfirm(null);
            resolve(false);
          },
        });
      }),
    []
  );

  const calcRequestRef = useRef(0);
  const pedidoEpochRef = useRef(0);
  const ventasSnapshotRef = useRef({});
  const catalogScrollRef = useRef(null);
  const productLockRef = useRef(createProductAddLock());
  const intentStoreRef = useRef(createIntentStore());
  const [agregandoIds, setAgregandoIds] = useState(() => new Set());
  const [lineaCancelar, setLineaCancelar] = useState(null);
  const [quitandoId, setQuitandoId] = useState(null);
  const [comentarioEdit, setComentarioEdit] = useState({});

  const usuario = useAuthStore((s) => s.user);
  const admin = isAdmin(usuario?.rol);
  const [searchParams] = useSearchParams();

  const lineasPedido = pedido?.lineas;
  const carrito = useMemo(() => lineasPedido ?? [], [lineasPedido]);
  const carritoActivo = useMemo(() => lineasActivas(carrito), [carrito]);

  const total = useMemo(
    () => sumaImportes(carritoActivo),
    [carritoActivo]
  );
  const subtotalNormal = pedido?.subtotal_normal;
  const descuentoPromos = pedido?.descuento_promociones;
  const resumenPromos = pedido?.resumen_promociones ?? [];

  const canjeCobro = useMemo(
    () => evaluarCanjeCliente(total, clienteCobro, puntosCanjeInput),
    [total, clienteCobro, puntosCanjeInput]
  );
  const aCubrir = canjeCobro.bloquea ? total : canjeCobro.importe;
  const cobroEfectivo = esEfectivo(formaPago) && aCubrir > 0;
  const montoRecibidoNum = parseFloat(montoRecibido);
  const cambioCobro = useMemo(() => {
    if (!cobroEfectivo || montoRecibido === "" || isNaN(montoRecibidoNum)) return null;
    return cambioEfectivo(montoRecibidoNum, aCubrir);
  }, [cobroEfectivo, montoRecibido, montoRecibidoNum, aCubrir]);
  const montoRecibidoInsuficiente =
    cobroEfectivo &&
    montoRecibido !== "" &&
    !isNaN(montoRecibidoNum) &&
    montoRecibidoNum < aCubrir;
  const cobroEfectivoInvalido =
    cobroEfectivo &&
    (montoRecibido === "" || isNaN(montoRecibidoNum) || montoRecibidoNum < aCubrir);
  const cobroBloqueado = canjeCobro.bloquea || cobroEfectivoInvalido;

  const lineasPendientesConfirmar = useMemo(
    () =>
      (lineasPedido ?? []).filter(
        (item) => !item.en_comanda && !esLineaCancelada(item)
      ),
    [lineasPedido]
  );

  const refrescarMesasActivas = useCallback(async (force = true) => {
    try {
      const { value } = await fetchMesasActivasCached({ force, allowStale: !force });
      setMesasActivas(value);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const actualizarMesasTrasAgregar = useCallback(
    (pedidoActualizado) => {
      if (modoParaLlevar || !numeroMesa) return;
      setMesasActivas((prev) =>
        mergeMesaActivaFromPedido(prev, numeroMesa, pedidoActualizado)
      );
    },
    [modoParaLlevar, numeroMesa]
  );

  const agregarLineaConCalculo = useCallback(
    async (producto, calculo, extras = [], cantidad = 1, comentario = null) => {
      const payload = {
        id_producto: producto.id_producto,
        cantidad,
        precio_unitario: Number(calculo.precio_unitario),
        precio_original: Number(calculo.precio_original_unitario),
        id_promocion: calculo.forzar_normal ? null : calculo.id_promocion,
        sin_promocion: Boolean(calculo.forzar_normal),
        extras,
        enviar_comanda: false,
        comentario: comentario?.trim() || null,
      };
      const fingerprint = fingerprintLinea({
        numeroMesa,
        paraLlevar: modoParaLlevar,
        ...payload,
      });
      const store = intentStoreRef.current;
      const operationId = store.beginIntent(fingerprint);
      try {
        const pedidoActualizado = await withIntentRetry(() =>
          agregarLineaPedido(
            numeroMesa,
            usuario.id_usuario,
            { ...payload, operation_id: operationId },
            modoParaLlevar
          )
        );
        store.completeIntent(fingerprint);
        pedidoEpochRef.current += 1;
        setPedido(pedidoActualizado);
        setCantidadEdit({});
        actualizarMesasTrasAgregar(pedidoActualizado);
        return pedidoActualizado;
      } catch (err) {
        if (!shouldKeepPendingKey(err)) {
          store.completeIntent(fingerprint);
        }
        throw err;
      }
    },
    [numeroMesa, usuario, modoParaLlevar, actualizarMesasTrasAgregar]
  );

  const ejecutarAgregadoRapido = useCallback(
    (producto, ctx) => {
      setPedido((prev) => {
        if (!prev?.id_pedido) return prev;
        const optimista = aplicarAgregadoOptimista(prev, producto, ctx.calculo_inicial);
        if (!optimista) return prev;
        queueMicrotask(() => actualizarMesasTrasAgregar(optimista));
        void agregarLineaConCalculo(producto, ctx.calculo_inicial).catch(async (err) => {
          toastError(formatApiError(err, "Error al agregar al pedido"));
          if (numeroMesa && usuario?.id_usuario) {
            try {
              const p = await getPedidoMesa(numeroMesa, usuario.id_usuario, modoParaLlevar);
              setPedido(p);
              actualizarMesasTrasAgregar(p);
            } catch {
              /* El toast ya informó; el cajero puede reintentar. */
            }
          }
        });
        return optimista;
      });
    },
    [
      agregarLineaConCalculo,
      actualizarMesasTrasAgregar,
      modoParaLlevar,
      numeroMesa,
      usuario?.id_usuario,
    ]
  );

  const resolverContextoProducto = useCallback(
    async (producto, ctx, { optimista = false } = {}) => {
      const paquetes = ctx.paquetes ?? [];
      const promos = ctx.promociones ?? [];
      const extras = ctx.extras ?? [];

      if (paquetes.length > 0) {
        setPromoConfirm({ kind: "combo", combo: paquetes[0], producto });
        return "promo";
      }
      if (promos.length > 0) {
        setPromoConfirm({ kind: "promo", promo: promos[0], producto });
        return "promo";
      }

      if (puedeAgregarRapido({ ...ctx, extras, promociones: promos, paquetes })) {
        if (optimista) {
          ejecutarAgregadoRapido(producto, ctx);
        } else {
          try {
            await agregarLineaConCalculo(producto, ctx.calculo_inicial);
          } catch (err) {
            toastError(formatApiError(err, "Error al agregar al pedido"));
          }
        }
        return "added";
      }

      setProductoModal(producto);
      setExtrasSeleccionados([]);
      setExtrasModal(extras);
      setPromosDisponibles(ctx.promociones ?? []);
      setPromoModo("auto");
      setCalculoInicialModal(ctx.calculo_inicial ?? null);
      setCalculoPromo(ctx.calculo_inicial ?? null);
      setCantidadModal("1");
      setComentarioModal("");
      setCargandoExtras(false);
      return "modal";
    },
    [agregarLineaConCalculo, ejecutarAgregadoRapido]
  );

  const handleAgregarMesa = async () => {
    try {
      setGestionMesasLoading(true);
      const data = await agregarMesa();
      setMesasLista(data.mesas);
    } catch (err) {
      const detail = err.response?.data?.detail;
      toastError(typeof detail === "string" ? detail : "No se pudo agregar la mesa");
    } finally {
      setGestionMesasLoading(false);
    }
  };

  const handleQuitarMesa = async (n, e) => {
    e?.stopPropagation();
    const activa = mesasActivas[n];
    if (activa?.num_lineas > 0) {
      toastError(`La mesa ${n} tiene un pedido abierto. Ciérrala antes de quitarla.`);
      return;
    }
    if (!(await askOperConfirm({ message: `¿Quitar la mesa ${n}?`, confirmLabel: "Quitar mesa" }))) return;
    try {
      setGestionMesasLoading(true);
      const data = await quitarMesa(n);
      setMesasLista(data.mesas);
      if (numeroMesa === n) {
        setNumeroMesa(null);
        setPedido(null);
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      toastError(typeof detail === "string" ? detail : "No se pudo quitar la mesa");
    } finally {
      setGestionMesasLoading(false);
    }
  };

  const cargarPedidoMesa = useCallback(async (mesa, paraLlevar = modoParaLlevar) => {
    if (!usuario?.id_usuario) return;
    const ticket = ++pedidoEpochRef.current;
    try {
      const p = await getPedidoMesa(mesa, usuario.id_usuario, paraLlevar);
      if (ticket !== pedidoEpochRef.current) return;
      setPedido(p);
      setCantidadEdit({});
      if (!paraLlevar) {
        refrescarMesasActivas(true).catch(console.error);
      }
    } catch (err) {
      console.error(err);
      toastError(
        paraLlevar ? "Error al cargar pedido para llevar" : "Error al cargar pedido de la mesa"
      );
    }
  }, [modoParaLlevar, usuario, refrescarMesasActivas]);

  const seleccionarMesa = useCallback(async (n) => {
    setNumeroMesa(n);
    await cargarPedidoMesa(n);
  }, [cargarPedidoMesa]);

  useEffect(() => {
    const uid = usuario?.id_usuario;
    if (!uid) return undefined;

    const snap = readVentasSession(uid, modoParaLlevar);
    if (snap) {
      if (snap.productos?.length) setProductos(snap.productos);
      if (snap.categorias?.length) setCategorias(snap.categorias);
      if (snap.tiposPosLabels) setTiposPosLabels(snap.tiposPosLabels);
      if (snap.mesasLista?.length) setMesasLista(snap.mesasLista);
      if (snap.mesasActivas) setMesasActivas(snap.mesasActivas);
      if (!modoParaLlevar && snap.numeroMesa) setNumeroMesa(snap.numeroMesa);
      if (snap.pedido) setPedido(snap.pedido);
      if (snap.categoriasAbiertas) setCategoriasAbiertas(snap.categoriasAbiertas);
      if (snap.busquedaProducto) setBusquedaProducto(snap.busquedaProducto);
      if (snap.pedido && snap.numeroMesa) {
        cargarPedidoMesa(snap.numeroMesa, modoParaLlevar).catch(console.error);
      }
      requestAnimationFrame(() => {
        if (snap.scrollY && catalogScrollRef.current) {
          catalogScrollRef.current.scrollTop = snap.scrollY;
        }
      });
    }

    let cancelled = false;
    (async () => {
      if (snap?.productos?.length) setRevalidandoShell(true);
      const { partial, errors } = await bootstrapVentasShell({ force: false });
      if (cancelled) return;
      if (partial.revalidating) setRevalidandoShell(true);
      if (partial.catalog?.value) {
        setProductos(partial.catalog.value.productos);
        setCategorias(partial.catalog.value.categorias);
        setTiposPosLabels(partial.catalog.value.tiposPosLabels);
      }
      if (partial.mesasLista?.value) setMesasLista(partial.mesasLista.value);
      if (partial.mesasActivas?.value) setMesasActivas(partial.mesasActivas.value);
      if (errors.length && !snap?.productos?.length) {
        toastError("Error al cargar el catálogo");
      }
      setRevalidandoShell(false);
    })();

    return () => {
      cancelled = true;
      writeVentasSession(uid, modoParaLlevar, ventasSnapshotRef.current);
    };
  }, [modoParaLlevar, usuario?.id_usuario, cargarPedidoMesa]);

  useEffect(() => {
    ventasSnapshotRef.current = {
      productos,
      categorias,
      tiposPosLabels,
      mesasLista,
      mesasActivas,
      numeroMesa,
      pedido,
      categoriasAbiertas,
      busquedaProducto,
      scrollY: catalogScrollRef.current?.scrollTop ?? 0,
    };
  }, [
    productos,
    categorias,
    tiposPosLabels,
    mesasLista,
    mesasActivas,
    numeroMesa,
    pedido,
    categoriasAbiertas,
    busquedaProducto,
  ]);

  useEffect(() => {
    if (!productos.length || !usuario?.id_usuario) return undefined;
    return schedulePrefetchProductoContextos(productos.map((p) => p.id_producto));
  }, [productos, usuario?.id_usuario]);

  useEffect(() => {
    if (!modoParaLlevar || !usuario?.id_usuario) return;
    setNumeroMesa(MESA_PARA_LLEVAR);
    cargarPedidoMesa(MESA_PARA_LLEVAR, true);
  }, [modoParaLlevar, usuario?.id_usuario, cargarPedidoMesa]);

  useEffect(() => {
    if (modoParaLlevar || !usuario?.id_usuario) return;
    const m = searchParams.get("mesa");
    if (!m) return;
    const n = parseInt(m, 10);
    if (!isNaN(n) && n > 0) {
      seleccionarMesa(n);
    }
  }, [searchParams, usuario?.id_usuario, modoParaLlevar, seleccionarMesa]);

  const productosPorCategoria = useMemo(() => {
    const q = busquedaProducto.trim().toLowerCase();
    const filtrados = productos.filter(
      (p) => !q || p.nombre.toLowerCase().includes(q)
    );

    const mapa = new Map();
    categorias.forEach((c) => {
      mapa.set(c.id_categoria, {
        id: c.id_categoria,
        nombre: c.nombre,
        productos: [],
      });
    });
    mapa.set(0, { id: 0, nombre: "Sin categoría", productos: [] });

    filtrados.forEach((p) => {
      const grupo = mapa.get(p.id_categoria) || mapa.get(0);
      grupo.productos.push(p);
    });

    return [...mapa.values()]
      .filter((g) => g.productos.length > 0)
      .map((g) => ({
        ...g,
        productos: g.productos.sort((a, b) =>
          a.nombre.localeCompare(b.nombre, "es")
        ),
      }));
  }, [productos, categorias, busquedaProducto]);

  useEffect(() => {
    if (!busquedaProducto.trim()) {
      setCategoriasAbiertas({});
      return;
    }
    const abiertas = {};
    productosPorCategoria.forEach((g) => {
      abiertas[g.id] = true;
    });
    setCategoriasAbiertas(abiertas);
  }, [busquedaProducto, productosPorCategoria]);

  const toggleCategoria = (id) => {
    setCategoriasAbiertas((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  useEffect(() => {
    if (!showCobroModal || total <= 0 || canjeCobro.bloquea) {
      if (!showCobroModal || total <= 0) setPuntosPreviewCobro(0);
      return;
    }
    const base = clienteCobro ? aCubrir : total;
    previewPuntos(base)
      .then((r) => setPuntosPreviewCobro(r.puntos_a_ganar))
      .catch(() => setPuntosPreviewCobro(0));
  }, [showCobroModal, total, clienteCobro, aCubrir, canjeCobro.bloquea]);

  const buscarClienteCobro = async (termino) => {
    const q = termino.trim();
    if (q.length < 2) {
      setResultadosCobro([]);
      return;
    }
    try {
      setBuscandoCobro(true);
      const data = await buscarClientes(q);
      setResultadosCobro(data.resultados || []);
    } catch (err) {
      console.error(err);
    } finally {
      setBuscandoCobro(false);
    }
  };

  useEffect(() => {
    if (!showCobroModal) return;
    const t = setTimeout(() => buscarClienteCobro(busquedaCobro), 300);
    return () => clearTimeout(t);
  }, [busquedaCobro, showCobroModal]);

  const seleccionarClienteCobro = (c) => {
    setClienteCobro(c);
    setBusquedaCobro("");
    setResultadosCobro([]);
  };

  const resolverQrCobro = async (codigoRaw) => {
    const c = parseCodigoFidelidad(codigoRaw);
    if (!c) {
      toastError("Código QR no válido. Debe ser CAFE- seguido de 6 caracteres.");
      return;
    }
    try {
      const cliente = await getClientePorCodigo(c);
      seleccionarClienteCobro(cliente);
      setQrCobro("");
      setShowQrScanner(false);
    } catch (err) {
      toastError(err.response?.data?.detail || "Cliente no encontrado");
      setQrCobro("");
    }
  };

  const guardarNuevoCliente = async () => {
    try {
      const c = await createCliente({ nombre: nuevoNombre, telefono: nuevoTelefono });
      seleccionarClienteCobro(c);
      setShowNuevoCliente(false);
      setNuevoNombre("");
      setNuevoTelefono("");
      setClienteQrRecienCreado(c);
    } catch (err) {
      toastError(err.response?.data?.detail || "Error al registrar cliente");
    }
  };

  const abrirCobroModal = () => {
    setClienteCobro(clientePrecargado(pedido));
    setBusquedaCobro("");
    setResultadosCobro([]);
    setQrCobro("");
    setMontoRecibido("");
    setFormaPago("EFECTIVO");
    setPuntosCanjeInput("");
    setShowCobroModal(true);
  };

  const imprimirPrecuenta = async () => {
    if (!pedido?.id_pedido || imprimiendoPrecuenta) return { ok: false, skipped: true };
    setImprimiendoPrecuenta(true);
    try {
      const printResult = await printTicketSafely(buildPrecuentaTicket, {
        pedido,
        usuario,
        subtotal: subtotalNormal ?? total,
        descuento: descuentoPromos ?? 0,
        total,
      });
      if (printResult.ok) {
        setPrecuentaImpresa(true);
      }
      return printResult;
    } finally {
      setImprimiendoPrecuenta(false);
    }
  };

  const handleReimprimirPrecuenta = async () => {
    const printResult = await imprimirPrecuenta();
    if (!printResult.skipped && !printResult.ok) {
      toastError(`Precuenta: ${printResult.message || "no se pudo imprimir"}`);
    }
  };

  const handleCerrarCuenta = async () => {
    if (!pedido?.id_pedido || carritoActivo.length === 0) return;
    if (imprimiendoPrecuenta || loading || showCobroModal) return;

    if (lineasPendientesConfirmar.length > 0) {
      if (modoParaLlevar) {
        const enviar = await askOperConfirm({
          title: "Enviar a comandera",
          message: `Hay ${lineasPendientesConfirmar.length} producto(s) sin enviar a comandera.\n\n¿Enviar a comandera ahora?`,
          confirmLabel: "Enviar a comandera",
        });
        if (!enviar) return;
        const ok = await confirmarPedidoComanda();
        if (!ok) return;
      } else {
        toastInfo("Confirma el pedido en comanda antes de cerrar la cuenta.");
        return;
      }
    }

    if (modoParaLlevar) {
      abrirCobroModal();
      return;
    }

    setPrecuentaImpresa(false);
    abrirCobroModal();
    if (canUseBluetoothPrinter()) {
      void imprimirPrecuenta().then((printResult) => {
        if (!printResult.skipped && !printResult.ok) {
          toastError(`Precuenta: ${printResult.message || "no se pudo imprimir"}`);
        }
      });
    }
  };

  const cerrarCobroModal = () => {
    setShowCobroModal(false);
    setBusquedaCobro("");
    setResultadosCobro([]);
    setQrCobro("");
    setMontoRecibido("");
    setPuntosCanjeInput("");
    setPrecuentaImpresa(false);
  };

  const extrasPorTipo = useMemo(() => {
    const grupos = {};
    for (const e of extrasModal) {
      const t = e.tipo || "OTRO";
      if (!grupos[t]) grupos[t] = [];
      grupos[t].push(e);
    }
    return grupos;
  }, [extrasModal]);

  const recalcularPromoModal = useCallback(async (producto, modoPromo, extras, cantidad, requestId) => {
    if (!producto) return;
    const cant = Number(cantidad);
    if (!cantidad || isNaN(cant) || cant < 1) {
      if (requestId === calcRequestRef.current) setCalculoPromo(null);
      return;
    }
    if (
      modoPromo === "auto" &&
      extras.length === 0 &&
      cant === 1 &&
      calculoInicialModal
    ) {
      if (requestId === calcRequestRef.current) setCalculoPromo(calculoInicialModal);
      return;
    }
    try {
      const payload = {
        id_producto: producto.id_producto,
        cantidad: cant,
        precio_extras: sumExtras(extras),
      };
      if (modoPromo === "none") {
        payload.sin_promocion = true;
      } else if (typeof modoPromo === "number") {
        payload.id_promocion = modoPromo;
      }
      const calc = await calcularPromocion(payload);
      if (requestId !== calcRequestRef.current) return;
      setCalculoPromo(calc);
    } catch (err) {
      if (requestId !== calcRequestRef.current) return;
      console.error(err);
      setCalculoPromo(null);
    }
  }, [calculoInicialModal]);

  useEffect(() => {
    if (!productoModal || cargandoExtras) return undefined;
    const requestId = ++calcRequestRef.current;
    const timer = setTimeout(() => {
      recalcularPromoModal(
        productoModal,
        promoModo,
        extrasSeleccionados,
        cantidadModal,
        requestId
      );
    }, 250);
    return () => clearTimeout(timer);
  }, [productoModal, promoModo, extrasSeleccionados, cantidadModal, recalcularPromoModal, cargandoExtras]);

  const abrirModalProducto = async (producto, opts = {}) => {
    if (!numeroMesa) {
      toastError(modoParaLlevar ? "Espera a que cargue el pedido" : "Primero selecciona el número de mesa");
      return;
    }
    setProductoModal(producto);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
    setPromosDisponibles([]);
    setPromoModo(opts.promoModo ?? "auto");
    setCalculoPromo(null);
    setCalculoInicialModal(null);
    setCantidadModal("1");
    setComentarioModal("");
    setCargandoExtras(true);
    try {
      const ctx = await getProductoContexto(producto.id_producto);
      setExtrasModal(ctx.extras ?? []);
      setPromosDisponibles(ctx.promociones ?? []);
      setCalculoInicialModal(ctx.calculo_inicial ?? null);
      const modo = opts.promoModo ?? "auto";
      if (modo === "auto" && ctx.calculo_inicial) {
        setCalculoPromo(ctx.calculo_inicial);
      }
    } catch (err) {
      console.error(err);
      toastError("Error al cargar opciones del producto");
      setProductoModal(null);
    } finally {
      setCargandoExtras(false);
    }
  };

  const handlePersonalizar = (producto, e) => {
    e?.stopPropagation?.();
    e?.preventDefault?.();
    abrirModalProducto(producto);
  };

  const handleProductoClick = async (producto) => {
    if (!numeroMesa) {
      toastError(modoParaLlevar ? "Espera a que cargue el pedido" : "Primero selecciona el número de mesa");
      return;
    }
    if (!usuario?.id_usuario) return;
    if (!productLockRef.current.tryBegin(producto.id_producto)) return;

    const liberarProducto = () => {
      productLockRef.current.end(producto.id_producto);
      setAgregandoIds((prev) => {
        if (!prev.has(producto.id_producto)) return prev;
        const next = new Set(prev);
        next.delete(producto.id_producto);
        return next;
      });
    };

    try {
      const cached = getCachedProductoContexto(producto.id_producto);
      if (cached) {
        await resolverContextoProducto(producto, cached, { optimista: true });
        return;
      }

      setAgregandoIds((prev) => {
        const next = new Set(prev);
        next.add(producto.id_producto);
        return next;
      });

      const ctx = await getProductoContexto(producto.id_producto);
      await resolverContextoProducto(producto, ctx, { optimista: true });
    } catch (err) {
      if (err?.code === "ERR_CANCELED") return;
      console.error("Contexto producto:", err.response?.status, err.response?.data?.detail);
      toastError(formatApiError(err, "Error al cargar opciones del producto"));
    } finally {
      liberarProducto();
    }
  };

  const cerrarPromoConfirm = () => setPromoConfirm(null);

  const rechazarPromoConfirm = () => {
    if (!promoConfirm) return;
    const { producto } = promoConfirm;
    cerrarPromoConfirm();
    abrirModalProducto(producto, { promoModo: "none" });
  };

  const aceptarPromoConfirm = async () => {
    if (!promoConfirm || !usuario?.id_usuario || !numeroMesa) return;

    if (promoConfirm.kind === "combo") {
      const { combo, producto } = promoConfirm;
      cerrarPromoConfirm();
      setGuardandoLinea(true);
      const comboPayload = {
        id_promocion: combo.id_promocion,
        cantidad: 1,
        enviar_comanda: false,
      };
      const fingerprint = fingerprintCombo({
        numeroMesa,
        paraLlevar: modoParaLlevar,
        ...comboPayload,
      });
      const store = intentStoreRef.current;
      const operationId = store.beginIntent(fingerprint);
      try {
        const pedidoActualizado = await withIntentRetry(() =>
          agregarComboPedido(
            numeroMesa,
            usuario.id_usuario,
            { ...comboPayload, operation_id: operationId },
            modoParaLlevar
          )
        );
        store.completeIntent(fingerprint);
        setPedido(pedidoActualizado);
        setCantidadEdit({});
        actualizarMesasTrasAgregar(pedidoActualizado);
      } catch (err) {
        if (!shouldKeepPendingKey(err)) {
          store.completeIntent(fingerprint);
        }
        toastError(formatApiError(err, "Error al agregar combo"));
        abrirModalProducto(producto, { promoModo: "none" });
      } finally {
        setGuardandoLinea(false);
      }
      return;
    }

    const { promo, producto } = promoConfirm;
    cerrarPromoConfirm();
    abrirModalProducto(producto, { promoModo: promo.id_promocion ?? "auto" });
  };

  const toggleExtra = (extra) => {
    setExtrasSeleccionados((prev) => {
      const existe = prev.find((e) => e.id_extra === extra.id_extra);
      if (existe) {
        return prev.filter((e) => e.id_extra !== extra.id_extra);
      }
      return [
        ...prev,
        {
          id_extra: extra.id_extra,
          nombre: extra.nombre,
          precio: Number(extra.precio),
          costo: Number(extra.costo || 0),
          id_insumo: extra.id_insumo ?? null,
          cantidad_insumo: Number(extra.cantidad_insumo ?? 1),
        },
      ];
    });
  };

  const confirmarAgregarAlCarrito = async () => {
    if (!productoModal || !calculoPromo || !numeroMesa || !usuario?.id_usuario) return;
    if (guardandoLinea) return;
    const cant = parseInt(cantidadModal, 10);
    if (!cantidadModal || isNaN(cant) || cant < 1) {
      toastError("Indica una cantidad mayor a 0");
      return;
    }
    if (!calculoPromo.margen_ok) {
      toastError(calculoPromo.mensaje || "La promoción no cumple el margen mínimo");
      return;
    }

    try {
      setGuardandoLinea(true);
      await agregarLineaConCalculo(
        productoModal,
        promoModo === "none" ? { ...calculoPromo, forzar_normal: true, id_promocion: null } : calculoPromo,
        extrasSeleccionados,
        cant,
        comentarioModal
      );
    } catch (err) {
      toastError(formatApiError(err, "Error al agregar al pedido"));
      return;
    } finally {
      setGuardandoLinea(false);
    }

    setProductoModal(null);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
    setPromosDisponibles([]);
    setPromoModo("auto");
    setCalculoPromo(null);
    setCalculoInicialModal(null);
    setCantidadModal("");
    setComentarioModal("");
  };

  const cambiarCantidad = async (idDetalle, value) => {
    const cant = parseInt(String(value).trim(), 10);
    if (isNaN(cant) || cant < 1 || !numeroMesa) return false;

    const linea = carrito.find((item) => item.id_detalle_pedido === idDetalle);
    if (linea && linea.cantidad === cant) return true;
    if (linea && requiereCancelacionEnviada(linea) && cant < Number(linea.cantidad)) {
      setLineaCancelar(linea);
      return false;
    }

    try {
      await actualizarLineaPedido(idDetalle, {
        cantidad: cant,
        cantidad_actual: linea?.cantidad,
      });
      await cargarPedidoMesa(numeroMesa, modoParaLlevar);
      return true;
    } catch (err) {
      if (debeRefrescarPedidoPorConflicto(err) && numeroMesa) {
        toastError(formatApiError(err, "Actualiza el pedido"));
        await cargarPedidoMesa(numeroMesa, modoParaLlevar);
        return false;
      }
      toastError(formatApiError(err, "Error al actualizar cantidad"));
      return false;
    }
  };

  const limpiarCantidadEdit = (idDetalle) => {
    setCantidadEdit((prev) => {
      if (!(idDetalle in prev)) return prev;
      const next = { ...prev };
      delete next[idDetalle];
      return next;
    });
  };

  const onCantidadLineaChange = (idDetalle, value) => {
    setCantidadEdit((prev) => ({ ...prev, [idDetalle]: value }));
  };

  const confirmarCantidadLinea = async (idDetalle) => {
    const raw = cantidadEdit[idDetalle];
    limpiarCantidadEdit(idDetalle);

    if (raw === undefined || raw === "") return;

    const cant = parseInt(String(raw).trim(), 10);
    if (isNaN(cant) || cant < 1) {
      toastError("La cantidad debe ser un número mayor a 0");
      return;
    }

    await cambiarCantidad(idDetalle, cant);
  };

  const guardarComentarioLinea = async (idDetalle) => {
    const raw = comentarioEdit[idDetalle];
    setComentarioEdit((prev) => {
      const next = { ...prev };
      delete next[idDetalle];
      return next;
    });
    const linea = carrito.find((item) => item.id_detalle_pedido === idDetalle);
    const nuevo = (raw ?? "").trim() || null;
    const actual = (linea?.comentario || "").trim() || null;
    if (nuevo === actual) return;
    try {
      await actualizarLineaPedido(idDetalle, { comentario: nuevo });
      await cargarPedidoMesa(numeroMesa, modoParaLlevar);
    } catch (err) {
      toastError(formatApiError(err, "Error al actualizar comentario"));
    }
  };

  const aplicarPedidoServidor = (pedidoActualizado) => {
    if (!pedidoActualizado) return;
    pedidoEpochRef.current += 1;
    setPedido(pedidoActualizado);
    setCantidadEdit({});
  };

  const eliminarDelCarrito = async (idDetalle) => {
    if (!numeroMesa || quitandoId === idDetalle) return;
    const linea = carrito.find((item) => item.id_detalle_pedido === idDetalle);
    const accion = accionQuitarLinea(linea);
    if (accion === "ninguna") return;
    if (accion === "cancelar_enviada") {
      if (!canCancelarProductoEnComanda(usuario)) {
        toastError("No tienes permiso para cancelar productos enviados.");
        return;
      }
      setLineaCancelar(linea);
      return;
    }
    setQuitandoId(idDetalle);
    try {
      await eliminarLineaPedido(idDetalle);
      await cargarPedidoMesa(numeroMesa, modoParaLlevar);
    } catch (err) {
      if (debeRefrescarPedidoPorConflicto(err)) {
        toastError(formatApiError(err, "Actualiza el pedido"));
        await cargarPedidoMesa(numeroMesa, modoParaLlevar);
        return;
      }
      toastError(formatApiError(err, "Error al eliminar línea"));
    } finally {
      setQuitandoId(null);
    }
  };

  const onCancelacionOk = async (pedidoActualizado, meta) => {
    setLineaCancelar(null);
    if (meta?.stale) {
      toastInfo(meta.message);
      await cargarPedidoMesa(numeroMesa, modoParaLlevar);
      return;
    }
    if (pedidoActualizado) {
      aplicarPedidoServidor(pedidoActualizado);
      return;
    }
    await cargarPedidoMesa(numeroMesa, modoParaLlevar);
  };

  const confirmarPedidoComanda = async () => {
    if (!pedido?.id_pedido) return false;
    if (lineasPendientesConfirmar.length === 0) {
      toastError("No hay productos pendientes de confirmar");
      return false;
    }
    try {
      setLoading(true);
      const pedidoActualizado = await confirmarComandaPedido(pedido.id_pedido);
      aplicarPedidoServidor(pedidoActualizado);
      invalidateMesasActivas();
      refrescarMesasActivas(true).catch(console.error);
      toastSuccess(
        modoParaLlevar ? "Pedido enviado a comandera" : "Pedido confirmado y enviado a comanda",
        { dedupeKey: "confirmar-comanda-ok" }
      );
      return true;
    } catch (err) {
      toastError(formatApiError(err, "Error al confirmar pedido"));
      return false;
    } finally {
      setLoading(false);
    }
  };

  const iniciarConfirmacionCobro = (conCliente) => {
    if (canjeCobro.bloquea) {
      toastError(canjeCobro.error);
      return;
    }
    if (!conCliente && canjeCobro.puntos > 0) {
      toastError("Selecciona el cliente para usar puntos");
      return;
    }
    if (cobroEfectivoInvalido) {
      toastError(`Indica cuánto paga el cliente (mínimo $${aCubrir.toFixed(2)})`);
      return;
    }
    if (modoParaLlevar && canUseBluetoothPrinter()) {
      setCobroPendiente({ conCliente });
      setShowImprimirTicketModal(true);
      return;
    }
    ejecutarCobro(conCliente, false);
  };

  const ejecutarCobro = async (conCliente, imprimirTicket = false, desasociarCliente = false, confirmarRecalculo = false) => {
    if (!usuario?.id_usuario || !pedido?.id_pedido) return;
    const usaCliente = Boolean(conCliente) && !desasociarCliente;

    if (!desasociarCliente && canjeCobro.bloquea) {
      toastError(canjeCobro.error);
      return;
    }
    if (!usaCliente && !desasociarCliente && canjeCobro.puntos > 0) {
      toastError("Selecciona el cliente para usar puntos");
      return;
    }
    if (cobroEfectivoInvalido) {
      toastError(`Indica cuánto paga el cliente (mínimo $${aCubrir.toFixed(2)})`);
      return;
    }

    const pagaCon = cobroEfectivo ? montoRecibidoNum : null;
    const cambio = cobroEfectivo ? cambioCobro : null;
    const payload = {
      ...payloadCobro({
        idUsuario: usuario.id_usuario,
        formaPago: !desasociarCliente && aCubrir === 0 ? "EFECTIVO" : formaPago,
        cliente: clienteCobro,
        conCliente: usaCliente,
        puntos: desasociarCliente ? 0 : canjeCobro.puntos,
        desasociarCliente,
        operationId: intentStoreRef.current.beginIntent(
          JSON.stringify({
            tipo: "cobro",
            id_pedido: pedido.id_pedido,
            id_cliente: usaCliente && clienteCobro ? clienteCobro.id_cliente : null,
            forma_pago: !desasociarCliente && aCubrir === 0 ? "EFECTIVO" : formaPago,
            puntos_canje: usaCliente && clienteCobro ? canjeCobro.puntos : 0,
            desasociar_cliente: desasociarCliente,
            confirmar_recalculo: Boolean(confirmarRecalculo),
          })
        ),
      }),
      confirmar_recalculo: Boolean(confirmarRecalculo),
    };
    const huellaCobro = JSON.stringify({
      tipo: "cobro",
      id_pedido: pedido.id_pedido,
      id_cliente: payload.id_cliente,
      forma_pago: payload.forma_pago,
      puntos_canje: payload.puntos_canje,
    });

    try {
      setLoading(true);
      const pedidoParaTicket = pedido;
      const res = await withIntentRetry(() => cobrarPedido(pedido.id_pedido, payload));
      intentStoreRef.current.completeIntent(huellaCobro);

      let printResult = { skipped: true };
      if (modoParaLlevar && imprimirTicket) {
        printResult = await printTicketSafely(buildCobroTicket, {
          venta: res,
          pedido: pedidoParaTicket,
          usuario,
          clienteNombre: usaCliente && clienteCobro ? clienteCobro.nombre : null,
          montoRecibido: pagaCon,
          cambio,
        });
      }

      const avisosInv = res.advertencias_inventario?.length
        ? res.advertencias_inventario
        : (res.advertencias_stock || []).map((texto) => ({ nombre: texto }));
      let printHint = null;
      if (!printResult.skipped && !printResult.ok) {
        printHint = `⚠ Impresión: ${printResult.message}`;
      } else if (!printResult.skipped && printResult.ok) {
        printHint = "Ticket impreso.";
      }
      cerrarCobroModal();
      setShowImprimirTicketModal(false);
      setCobroPendiente(null);
      pedidoEpochRef.current += 1;
      invalidateMesasActivas();
      const mesaCobradaRef = numeroMesa;
      const resumenPostCobro = {
        venta: res,
        modoParaLlevar,
        numeroMesa: mesaCobradaRef,
        segundosEnMesa: pedidoParaTicket?.fecha_apertura
          ? segundosEnMesa(pedidoParaTicket.fecha_apertura)
          : null,
        pagaCon: cobroEfectivo ? pagaCon : null,
        cambio: cobroEfectivo ? cambio : null,
        advertenciasInventario: avisosInv,
        printHint,
        clienteNombre: usaCliente && clienteCobro ? clienteCobro.nombre : null,
      };
      if (modoParaLlevar) {
        setPedido(null);
      } else {
        setPedido(null);
        setNumeroMesa(null);
        setMesasActivas((prev) => {
          const next = { ...prev };
          if (mesaCobradaRef) delete next[mesaCobradaRef];
          return next;
        });
      }
      showCobroExitoResumen(resumenPostCobro);
      if (modoParaLlevar) {
        void cargarPedidoMesa(MESA_PARA_LLEVAR, true).catch(console.error);
      } else {
        void refrescarMesasActivas(true).catch(console.error);
      }
    } catch (err) {
      console.error(err);
      if (!shouldKeepPendingKey(err)) {
        intentStoreRef.current.completeIntent(huellaCobro);
      }
      const status = err.response?.status;
      const cuerpo = err.response?.data;
      const efecto = resolverErrorCobro(status, cuerpo);
      if (efecto.saldoActual != null && clienteCobro) {
        setClienteCobro((prev) => (prev ? { ...prev, puntos_saldo: efecto.saldoActual } : prev));
        setPuntosCanjeInput("");
      }
      if (efecto.refrescaSaldo && clienteCobro?.id_cliente) {
        try {
          const fresco = await getCliente(clienteCobro.id_cliente);
          if (fresco) setClienteCobro(fresco);
        } catch {
          /* El pedido sigue abierto con el saldo que ya se mostraba. */
        }
      }
      if (status === 409) {
        const texto =
          (typeof cuerpo?.detail === "string" && cuerpo.detail) ||
          cuerpo?.detail?.detail ||
          "Ese cobro ya se usó con otros datos. El pedido sigue abierto si no se registró.";
        if (efecto.codigo === "RECALCULO" && !confirmarRecalculo) {
          const aviso =
            (typeof cuerpo?.detail === "object" && cuerpo.detail?.detail) ||
            (typeof texto === "string" && texto) ||
            "El total cambió. Confirma el nuevo total.";
          setRecalculoConfirm({
            message: aviso,
            onConfirm: () => {
              setRecalculoConfirm(null);
              ejecutarCobro(conCliente, imprimirTicket, desasociarCliente, true);
            },
          });
          return;
        }
        toastError(texto);
        return;
      }
      toastError(formatApiError(err, "Error al cobrar"));
    } finally {
      setLoading(false);
    }
  };

  const ventasHabilitadas = Boolean(numeroMesa);

  return (
    <div
      className="page page--ventas"
      data-nav-shell="ventas"
      data-nav-catalog={productos.length ? "ready" : "pending"}
      data-nav-mesas={mesasLista.length ? "ready" : "pending"}
      data-nav-pedido={pedido && numeroMesa ? "ready" : "pending"}
      data-nav-mesa-seleccionada={numeroMesa != null ? String(numeroMesa) : ""}
      data-nav-total-ready={pedido && carritoActivo.length >= 0 ? "ready" : "pending"}
    >
      {revalidandoShell && (
        <p className="hint ventas-revalidando" data-nav-revalidating="1">
          Actualizando…
        </p>
      )}
      <PageHeader
        title={modoParaLlevar ? "Venta para llevar" : "Punto de venta"}
        subtitle={
          modoParaLlevar
            ? "Mismo catálogo que ventas en mesa — al cobrar se descuenta inventario"
            : "Pedidos por mesa — al cobrar puedes asignar cliente y puntos"
        }
      />

      {canUseBluetoothPrinter() && (
        <div style={{ marginBottom: "1rem" }}>
          <button
            type="button"
            className="btn btn--secondary inline-flex items-center gap-2"
            onClick={() => setShowPrinterSettings(true)}
          >
            <HiOutlinePrinter className="size-5" aria-hidden />
            Impresora
            {getSavedPrinter()?.name ? (
              <span className="hint">({getSavedPrinter().name})</span>
            ) : (
              <span className="hint">(sin configurar)</span>
            )}
          </button>
        </div>
      )}

      <PrinterSettings
        open={showPrinterSettings}
        onClose={() => setShowPrinterSettings(false)}
      />

      {!modoParaLlevar && (
        <section className="ventas-mesas-bar">
          <div className="ventas-mesas-bar__top">
            <span className="ventas-mesas-bar__label inline-flex items-center gap-1.5">
              <HiOutlineTableCells className="size-5 text-olive" aria-hidden />
              Selecciona mesa
            </span>
            <div className="ventas-mesas-bar__actions">
              {numeroMesa && (
                <span className="ventas-mesas-bar__actual">Mesa {numeroMesa} activa</span>
              )}
              {admin && (
                <button
                  type="button"
                  className={`btn btn--ghost btn--sm ${editandoMesas ? "btn--active" : ""}`}
                  onClick={() => setEditandoMesas((v) => !v)}
                  disabled={gestionMesasLoading}
                >
                  {editandoMesas ? "Listo" : "Gestionar mesas"}
                </button>
              )}
            </div>
          </div>
          <div className="ventas-mesas-grid">
            {mesasLista.map((n) => {
              const activa = mesasActivas[n];
              const ocupada = activa && activa.num_lineas > 0;
              return (
                <div key={n} className="mesa-card-wrap">
                  <button
                    type="button"
                    onClick={() => !editandoMesas && seleccionarMesa(n)}
                    disabled={editandoMesas && gestionMesasLoading}
                    className={`mesa-card ${numeroMesa === n ? "mesa-card--active" : ""} ${ocupada ? "mesa-card--ocupada" : ""} ${editandoMesas ? "mesa-card--edit" : ""}`}
                  >
                    <HiOutlineTableCells className="mesa-card__icon" aria-hidden />
                    <span className="mesa-card__num">{n}</span>
                    <span className="mesa-card__text">Mesa</span>
                    {ocupada && !editandoMesas && (
                      <span className="mesa-card__badge">{activa.num_lineas}</span>
                    )}
                  </button>
                  {editandoMesas && admin && (
                    <button
                      type="button"
                      className="mesa-card__remove"
                      title={`Quitar mesa ${n}`}
                      disabled={gestionMesasLoading || mesasLista.length <= 1}
                      onClick={(e) => handleQuitarMesa(n, e)}
                    >
                      <HiOutlineXMark className="size-4" aria-hidden />
                    </button>
                  )}
                </div>
              );
            })}
            {editandoMesas && admin && (
              <button
                type="button"
                className="mesa-card mesa-card--add"
                onClick={handleAgregarMesa}
                disabled={gestionMesasLoading}
              >
                <HiOutlinePlus className="mesa-card__icon" aria-hidden />
                <span className="mesa-card__text">Agregar</span>
              </button>
            )}
          </div>
          {editandoMesas && admin && (
            <p className="hint ventas-mesas-bar__hint">
              Agrega o quita mesas. No puedes quitar una mesa con pedido abierto.
            </p>
          )}
        </section>
      )}

      <div className={`ventas-workspace ${!ventasHabilitadas ? "ventas-workspace--disabled" : ""}`}>
        <section className="ventas-catalogo-panel">
          <div className="ventas-catalogo-panel__head">
            <h2>{modoParaLlevar ? "Productos" : "Catálogo"}</h2>
            {!ventasHabilitadas && !modoParaLlevar && (
              <p className="hint">Selecciona una mesa</p>
            )}
          </div>
          <div className="ventas-catalogo" ref={catalogScrollRef}>
            <SearchField
              value={busquedaProducto}
              onChange={(e) => setBusquedaProducto(e.target.value)}
              placeholder="Buscar producto por nombre..."
              disabled={!ventasHabilitadas}
            />

            {productos.length === 0 ? (
              <p className="empty-state" style={{ marginTop: "0.75rem" }}>
                No hay productos en el catálogo. Agrega categorías y productos en el módulo{" "}
                <strong>Productos</strong> del menú lateral.
              </p>
            ) : productosPorCategoria.length === 0 ? (
              <p className="empty-state" style={{ marginTop: "0.75rem" }}>
                No hay productos que coincidan con la búsqueda
              </p>
            ) : (
              <div className="ventas-categorias-list">
                {productosPorCategoria.map((grupo) => {
                  const abierta = categoriasAbiertas[grupo.id] === true;
                  return (
                    <div key={grupo.id} className="ventas-categoria">
                      <button
                        type="button"
                        className="ventas-categoria__header"
                        onClick={() => toggleCategoria(grupo.id)}
                      >
                        <span className="ventas-categoria__title">
                          <span className="ventas-categoria__chevron">{abierta ? "−" : "+"}</span>
                          {grupo.nombre}
                        </span>
                        <span className="ventas-categoria__count">{grupo.productos.length}</span>
                      </button>
                      {abierta && (
                        <div className="ventas-productos-list">
                          {grupo.productos.map((p) => (
                            <div key={p.id_producto} className="ventas-producto-row">
                              <button
                                type="button"
                                className={`ventas-producto-item${
                                  agregandoIds.has(p.id_producto) ? " ventas-producto-item--busy" : ""
                                }`}
                                onClick={() => handleProductoClick(p)}
                                disabled={
                                  !ventasHabilitadas ||
                                  agregandoIds.has(p.id_producto)
                                }
                                aria-busy={agregandoIds.has(p.id_producto) || undefined}
                              >
                                <span className="ventas-producto-item__main">
                                  <span className="ventas-producto-item__dot" aria-hidden />
                                  <span className="ventas-producto-item__nombre">{p.nombre}</span>
                                </span>
                                <span className="ventas-producto-item__precio">
                                  ${Number(p.precio_venta).toFixed(2)}
                                </span>
                              </button>
                              <button
                                type="button"
                                className="ventas-producto-item__personalizar"
                                onClick={(e) => handlePersonalizar(p, e)}
                                disabled={!ventasHabilitadas || agregandoIds.has(p.id_producto)}
                                aria-label={`Personalizar ${p.nombre}`}
                                title="Cantidad y comentario"
                              >
                                Personalizar
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        <aside className="cart-panel cart-panel--pos">
          <header className="cart-panel__head">
            <h2 className="flex items-center gap-2">
              {modoParaLlevar ? (
                <HiOutlineShoppingBag className="size-5 shrink-0" aria-hidden />
              ) : (
                <HiOutlineShoppingCart className="size-5 shrink-0" aria-hidden />
              )}
              {modoParaLlevar
                ? "Pedido para llevar"
                : `Pedido ${numeroMesa ? `(Mesa ${numeroMesa})` : ""}`}
            </h2>
            {carritoActivo.length > 0 && (
              <span className="cart-panel__count">
                {carritoActivo.length} {carritoActivo.length === 1 ? "producto" : "productos"}
              </span>
            )}
          </header>
          {carrito.length === 0 ? (
            <div className="cart-panel__items">
              <p className="empty-state">Sin productos en el pedido</p>
            </div>
          ) : (
            <div className="cart-panel__items">
              {carrito.map((item) => {
                const cancelada = esLineaCancelada(item);
                const enviada = requiereCancelacionEnviada(item);
                return (
                <article
                  key={item.id_detalle_pedido}
                  className={`cart-item${cancelada ? " cart-item--cancelada" : ""}`}
                >
                  <div className="cart-item__row-main">
                    <h3 className="cart-item__title">{item.nombre_producto}</h3>
                    <span className="cart-item__amount">${importeLinea(item).toFixed(2)}</span>
                  </div>
                  {(item.nombre_promocion ||
                    cancelada ||
                    (!cancelada && !item.en_comanda && !modoParaLlevar) ||
                    (!cancelada && item.cantidad_pendiente > 0 && item.en_comanda) ||
                    (item.en_comanda && item.cantidad_pendiente > 0 && item.fecha_envio_comanda && !cancelada) ||
                    item.comentario) && (
                    <div className="cart-item__sub">
                      {item.nombre_promocion && (
                        <span className="badge">{item.nombre_promocion}</span>
                      )}
                      {cancelada && <span className="badge badge--danger">CANCELADO</span>}
                      {!cancelada && !item.en_comanda && !modoParaLlevar && (
                        <span className="badge badge--pending">sin confirmar</span>
                      )}
                      {!cancelada && item.cantidad_pendiente > 0 && item.en_comanda && (
                        <span className="badge badge--kitchen">en comanda</span>
                      )}
                      {item.en_comanda && item.cantidad_pendiente > 0 && item.fecha_envio_comanda && !cancelada && (
                        <ElapsedTimer since={item.fecha_envio_comanda} />
                      )}
                      {item.comentario && (
                        <span className="cart-item__comentario" title={item.comentario}>
                          📝 {item.comentario}
                        </span>
                      )}
                    </div>
                  )}
                  {item.extras?.length > 0 && (
                    <ul className="cart-item__extras">
                      {item.extras.map((e) => (
                        <li key={e.id_extra}>
                          + {e.nombre}
                          {Number(e.precio) > 0 && ` ($${Number(e.precio).toFixed(2)})`}
                          {admin && Number(e.costo) > 0 && (
                            <span className="hint"> · costo ${Number(e.costo).toFixed(2)}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {!cancelada && comentarioEdit[item.id_detalle_pedido] !== undefined && (
                    <div className="cart-item__comentario-edit">
                      <textarea
                        className="input"
                        rows={2}
                        maxLength={300}
                        value={comentarioEdit[item.id_detalle_pedido]}
                        onChange={(e) =>
                          setComentarioEdit((prev) => ({
                            ...prev,
                            [item.id_detalle_pedido]: e.target.value,
                          }))
                        }
                        onBlur={() => guardarComentarioLinea(item.id_detalle_pedido)}
                        placeholder="Comentario para cocina"
                      />
                    </div>
                  )}
                  <div className="cart-item__toolbar">
                    <p className="cart-item__unit">
                      {Array.isArray(item.desglose) && item.desglose.length > 0
                        ? item.desglose
                            .map((parte) => `${parte.etiqueta} $${Number(parte.importe).toFixed(2)}`)
                            .join(" · ")
                        : (item.descuento_unitario ?? 0) > 0 && Number(item.unidades_normales || 0) === 0
                          ? `$${Number(item.precio_original).toFixed(2)} → $${Number(item.precio_unitario).toFixed(2)} c/u`
                          : `$${Number(item.precio_unitario).toFixed(2)} c/u`}
                    </p>
                    <div className="cart-item__controls">
                      {!cancelada && comentarioEdit[item.id_detalle_pedido] === undefined && (
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm cart-item__icon-btn cart-item__nota-btn"
                          onClick={() =>
                            setComentarioEdit((prev) => ({
                              ...prev,
                              [item.id_detalle_pedido]: item.comentario || "",
                            }))
                          }
                          aria-label={item.comentario ? "Editar nota" : "Agregar nota"}
                          title="Nota para cocina"
                        >
                          <HiOutlinePencilSquare className="size-4" aria-hidden />
                        </button>
                      )}
                      <input
                        type="number"
                        min="1"
                        value={cantidadEdit[item.id_detalle_pedido] ?? item.cantidad}
                        onChange={(e) =>
                          onCantidadLineaChange(item.id_detalle_pedido, e.target.value)
                        }
                        onFocus={(e) => e.target.select()}
                        onBlur={() => confirmarCantidadLinea(item.id_detalle_pedido)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") e.currentTarget.blur();
                        }}
                        className="input cart-item__qty"
                        disabled={cancelada || enviada}
                        readOnly={enviada}
                        aria-label={`Cantidad ${item.nombre_producto}`}
                        title={enviada ? "Para reducir una línea en comanda, registra una cancelación" : undefined}
                      />
                      {!cancelada && (
                        <button
                          type="button"
                          className="btn btn--danger cart-item__remove"
                          onClick={() => eliminarDelCarrito(item.id_detalle_pedido)}
                          disabled={quitandoId === item.id_detalle_pedido}
                          aria-label={enviada ? "Cancelar producto enviado" : "Quitar"}
                        >
                          {quitandoId === item.id_detalle_pedido ? "…" : "✕"}
                        </button>
                      )}
                    </div>
                  </div>
                </article>
                );
              })}
            </div>
          )}

          <div className="cart-panel__footer">
          {pedido?.aviso_recalculo && (
            <p className="hint" style={{ marginBottom: "0.5rem" }}>
              {pedido.aviso_recalculo}
            </p>
          )}
          {(subtotalNormal > 0 && descuentoPromos > 0) ? (
            <div className="cart-totals-breakdown" style={{ marginBottom: "0.5rem" }}>
              <div className="hint" style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Subtotal</span>
                <span>${Number(subtotalNormal).toFixed(2)}</span>
              </div>
              {resumenPromos.map((p) => (
                <div key={p.id_promocion} className="hint" style={{ display: "flex", justifyContent: "space-between", color: "var(--olive-dark)" }}>
                  <span>{p.nombre}</span>
                  <span>-${Number(p.descuento || 0).toFixed(2)}</span>
                </div>
              ))}
              {!resumenPromos.length && (
                <div className="hint" style={{ display: "flex", justifyContent: "space-between", color: "var(--olive-dark)" }}>
                  <span>Descuento promociones</span>
                  <span>-${Number(descuentoPromos).toFixed(2)}</span>
                </div>
              )}
            </div>
          ) : null}
          <div className="cart-total">
            <span className="cart-total__label">Total</span>
            <span>${total.toFixed(2)}</span>
          </div>
          <div className="cart-panel__actions">
          {!modoParaLlevar && (
            <button
              type="button"
              className="btn btn--accent inline-flex w-full items-center justify-center gap-2"
              onClick={confirmarPedidoComanda}
              disabled={
                loading ||
                carritoActivo.length === 0 ||
                !numeroMesa ||
                lineasPendientesConfirmar.length === 0
              }
            >
              <HiOutlineCheckBadge className="size-5 shrink-0" aria-hidden />
              Confirmar pedido ({lineasPendientesConfirmar.length})
            </button>
          )}
          {modoParaLlevar && lineasPendientesConfirmar.length > 0 && (
            <button
              type="button"
              className="btn btn--accent inline-flex w-full items-center justify-center gap-2"
              onClick={confirmarPedidoComanda}
              disabled={loading || carritoActivo.length === 0 || !numeroMesa}
            >
              <HiOutlineCheckBadge className="size-5 shrink-0" aria-hidden />
              Confirmar pedido / Enviar a comandera ({lineasPendientesConfirmar.length})
            </button>
          )}
          <button
            type="button"
            className="btn btn--success inline-flex w-full items-center justify-center gap-2"
            onClick={handleCerrarCuenta}
            disabled={loading || imprimiendoPrecuenta || showCobroModal || carritoActivo.length === 0 || !numeroMesa}
          >
            <HiOutlineBanknotes className="size-5 shrink-0" aria-hidden />
            {modoParaLlevar ? "Cobrar para llevar" : "Cerrar cuenta / Cobrar"}
          </button>
          </div>
          </div>
        </aside>
      </div>

      {promoConfirm && (
        <div className="modal-overlay" onClick={cerrarPromoConfirm}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h2>¿Aplicar promoción?</h2>
            {promoConfirm.kind === "combo" ? (
              <>
                <p style={{ marginBottom: "0.5rem" }}>
                  <strong>{promoConfirm.combo.nombre}</strong>
                </p>
                <p className="hint" style={{ marginBottom: "0.75rem" }}>
                  {(promoConfirm.combo.productos || [])
                    .map((p) => p.nombre)
                    .join(" + ")}
                </p>
                <p>
                  Precio del paquete:{" "}
                  <strong>${Number(promoConfirm.combo.valor).toFixed(2)}</strong>
                </p>
                <p className="hint" style={{ marginTop: "0.75rem" }}>
                  Sí = se agregan todos los productos del combo.
                  No = solo {promoConfirm.producto.nombre} a precio normal.
                </p>
              </>
            ) : (
              <>
                <p style={{ marginBottom: "0.5rem" }}>
                  Promoción: <strong>{promoConfirm.promo.nombre}</strong>
                </p>
                <p className="hint">Producto: {promoConfirm.producto.nombre}</p>
                <p className="hint" style={{ marginTop: "0.75rem" }}>
                  Sí = con promoción. No = precio normal.
                </p>
              </>
            )}
            <div
              className="btn-group"
              style={{ marginTop: "1.25rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}
            >
              <button
                type="button"
                className="btn btn--secondary"
                style={{ flex: 1, minWidth: "8rem" }}
                onClick={rechazarPromoConfirm}
                disabled={loading}
              >
                No, precio normal
              </button>
              <button
                type="button"
                className="btn btn--primary"
                style={{ flex: 1, minWidth: "8rem" }}
                onClick={aceptarPromoConfirm}
                disabled={loading}
              >
                Sí, aplicar
              </button>
            </div>
          </div>
        </div>
      )}

      {productoModal && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h2>{productoModal.nombre}</h2>
            <p className="hint">
              Precio base ${Number(productoModal.precio_venta).toFixed(2)}
              {modoParaLlevar ? " · Para llevar" : ` · Mesa ${numeroMesa}`}
            </p>
            {!cargandoExtras && calculoPromo?.nombre_promocion && (
              <div
                className="badge badge--ok"
                style={{ marginBottom: "1rem", display: "inline-block" }}
              >
                Promo: {calculoPromo.nombre_promocion}
                {calculoPromo.descuento_unitario > 0 &&
                  Number(calculoPromo.unidades_normales || 0) === 0 &&
                  Number(calculoPromo.aplicaciones || 0) === 0 && (
                  <> · -${Number(calculoPromo.descuento_unitario).toFixed(2)} c/u</>
                )}
              </div>
            )}

            {!cargandoExtras && promosDisponibles.length > 0 && (
              <div style={{ marginBottom: "1rem" }}>
                <label className="hint">Promoción</label>
                <select
                  className="select"
                  aria-label="Promoción"
                  value={
                    promoModo === "auto"
                      ? "auto"
                      : promoModo === "none"
                        ? "none"
                        : String(promoModo)
                  }
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === "auto") setPromoModo("auto");
                    else if (val === "none") setPromoModo("none");
                    else setPromoModo(Number(val));
                  }}
                >
                  <option value="auto">Automática (mejor precio)</option>
                  <option value="none">{OPCION_PRECIO_NORMAL}</option>
                  {promosDisponibles.map((p) => (
                    <option key={p.id_promocion} value={p.id_promocion}>
                      {p.nombre} ({p.tipo === "PORCENTAJE" ? `${p.valor}%` : p.tipo === "CANTIDAD_PRECIO" ? `${p.cantidad_requerida} x $${Number(p.valor).toFixed(2)}` : p.tipo})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="form-row" style={{ marginBottom: "1rem" }}>
              <label>Cantidad</label>
              <input
                type="number"
                min="1"
                value={cantidadModal}
                onChange={(e) => setCantidadModal(e.target.value)}
                className="input"
                style={{ width: 80 }}
                placeholder="Cant."
              />
            </div>

            <div className="form-row" style={{ marginBottom: "1rem" }}>
              <label>Comentario para cocina (opcional)</label>
              <textarea
                className="input"
                rows={2}
                maxLength={300}
                placeholder="Ej. sin azúcar, extra caliente..."
                value={comentarioModal}
                onChange={(e) => setComentarioModal(e.target.value)}
              />
            </div>

            <p style={{ fontSize: "0.9rem" }}>Extras opcionales:</p>

            {cargandoExtras && <p className="hint">Cargando opciones…</p>}
            {!cargandoExtras && extrasModal.length === 0 && (
              <p className="empty-state" style={{ textAlign: "left", padding: "0.5rem 0" }}>
                Sin extras para esta categoría. Configúralos en Extras de venta.
              </p>
            )}

            {!cargandoExtras &&
              Object.entries(extrasPorTipo).map(([tipo, lista]) => (
                <div key={tipo} style={{ marginBottom: "1rem" }}>
                  <div style={{ fontWeight: 600, marginBottom: "0.4rem", fontSize: "0.85rem" }}>
                    {tiposPosLabels[tipo] || tipo}
                  </div>
                  <div className="extra-chips">
                    {lista.map((extra) => {
                    const sel = extrasSeleccionados.some(
                      (e) => e.id_extra === extra.id_extra
                    );
                    return (
                      <button
                        key={extra.id_extra}
                          type="button"
                          onClick={() => toggleExtra(extra)}
                          className={`extra-chip ${sel ? "extra-chip--selected" : ""}`}
                        >
                          {extra.nombre}
                          {Number(extra.precio) > 0 && (
                            <span className="extra-chip__precio">
                              +${Number(extra.precio).toFixed(2)}
                            </span>
                          )}
                          {admin && Number(extra.costo) > 0 && (
                            <span className="hint" style={{ display: "block", fontSize: "0.75rem" }}>
                              Costo ${Number(extra.costo).toFixed(2)}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}

            {!cargandoExtras && calculoPromo && (
              <div className="price-preview">
                <PrecioPromoLinea calc={calculoPromo} />
                {!calculoPromo.margen_ok && (
                  <p style={{ color: "var(--color-danger, #c0392b)" }}>
                    {calculoPromo.mensaje}
                  </p>
                )}
              </div>
            )}

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  setProductoModal(null);
                  setExtrasSeleccionados([]);
                  setExtrasModal([]);
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={confirmarAgregarAlCarrito}
                disabled={!calculoPromo || !calculoPromo.margen_ok || guardandoLinea || loading}
              >
                {guardandoLinea ? "Agregando…" : "Agregar al pedido"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showCobroModal && (
        <div className="modal-overlay" onClick={cerrarCobroModal}>
          <div className="modal-box modal-box--wide modal-box--cobro" onClick={(e) => e.stopPropagation()}>
            <div className="modal-cobro-body">
            <h2>{modoParaLlevar ? "Registrar pago — Para llevar" : `Registrar pago — Mesa ${numeroMesa}`}</h2>
            {!modoParaLlevar && precuentaImpresa && (
              <p className="hint">La precuenta ya fue impresa. Selecciona la forma de pago.</p>
            )}
            {(modoParaLlevar || !precuentaImpresa) && (
              <p className="hint">Selecciona la forma de pago.</p>
            )}
            <p className="cart-total" style={{ margin: "0.5rem 0 1rem" }}>
              Total: ${total.toFixed(2)}
            </p>

            {ocultaMetodoMonetario(canjeCobro) ? (
              <p className="hint panel-muted" style={{ marginBottom: "1rem" }}>
                Pago total con puntos. No hay efectivo, transferencia ni terminal.
              </p>
            ) : (
            <div className="form-row">
              <label>Forma de pago</label>
              <select
                className="select"
                value={formaPago}
                onChange={(e) => {
                  setFormaPago(e.target.value);
                  if (!esEfectivo(e.target.value)) setMontoRecibido("");
                }}
              >
                {FORMAS_PAGO.map((fp) => (
                  <option key={fp.value} value={fp.value}>
                    {fp.label}
                  </option>
                ))}
              </select>
            </div>
            )}

            {formaPago === "TRANSFERENCIA" && aCubrir > 0 && (
              <p className="hint panel-muted" style={{ marginBottom: "1rem" }}>
                Pago por <strong>Transferencia</strong>
                {canjeCobro.puntos > 0 ? ` de $${aCubrir.toFixed(2)}` : ""}. No se solicita importe recibido ni cambio.
              </p>
            )}
            {formaPago === "TARJETA" && aCubrir > 0 && (
              <p className="hint panel-muted" style={{ marginBottom: "1rem" }}>
                Pago con <strong>Terminal</strong>
                {canjeCobro.puntos > 0 ? ` de $${aCubrir.toFixed(2)}` : ""}. No se solicita importe recibido ni cambio.
              </p>
            )}
            {ocultaMetodoMonetario(canjeCobro) && (
              <p className="hint panel-muted" style={{ marginBottom: "1rem" }}>
                El ticket queda cubierto con puntos. No hay importe monetario.
              </p>
            )}

            {cobroEfectivo && (
              <>
                <div className="form-row">
                  <label htmlFor="monto-recibido">Paga con</label>
                  <input
                    id="monto-recibido"
                    type="number"
                    className="input"
                    min="0"
                    step="0.01"
                    value={montoRecibido}
                    onChange={(e) => setMontoRecibido(e.target.value)}
                    placeholder={`Mín. $${aCubrir.toFixed(2)}`}
                    autoFocus
                  />
                </div>
                {montoRecibido !== "" && !isNaN(montoRecibidoNum) && (
                  <div
                    className="panel-muted"
                    style={{
                      marginBottom: "1rem",
                      borderColor: montoRecibidoInsuficiente
                        ? "var(--berry)"
                        : "var(--olive-pale)",
                    }}
                  >
                    {montoRecibidoInsuficiente ? (
                      <p style={{ margin: 0, color: "var(--berry)" }}>
                        Falta ${(aCubrir - montoRecibidoNum).toFixed(2)} para cubrir el resto
                      </p>
                    ) : (
                      <p style={{ margin: 0 }}>
                        Cambio:{" "}
                        <strong style={{ fontSize: "1.25rem", color: "var(--olive)" }}>
                          ${cambioCobro.toFixed(2)}
                        </strong>
                      </p>
                    )}
                  </div>
                )}
              </>
            )}

            <hr style={{ border: "none", borderTop: "1px solid var(--cream-dark)", margin: "1.25rem 0" }} />

            <h3 style={{ marginTop: 0, fontSize: "1.05rem" }}>¿Cliente frecuente? (puntos)</h3>
            <p className="hint">Opcional — busca por teléfono, nombre o escanea QR</p>

            {clienteCobro ? (
              <div className="cliente-seleccionado card" style={{ marginBottom: "1rem" }}>
                <div>
                  <strong>{clienteCobro.nombre}</strong>
                  <span className="hint"> · {clienteCobro.telefono}</span>
                  <br />
                  <span className="badge">Saldo: {clienteCobro.puntos_saldo} pts</span>
                  {puntosPreviewCobro > 0 && (
                    <span className="hint" style={{ marginLeft: "0.5rem" }}>
                      → <strong>+{puntosPreviewCobro} pts</strong> en esta cuenta
                    </span>
                  )}
                </div>
                {canjeCobro.habilitado ? (
                  <div className="form-row" style={{ marginTop: "0.75rem" }}>
                    <label htmlFor="puntos-canje">Usar puntos</label>
                    <input
                      id="puntos-canje"
                      type="number"
                      className="input"
                      min="0"
                      step="10"
                      value={puntosCanjeInput}
                      onChange={(e) => setPuntosCanjeInput(e.target.value)}
                      placeholder={`Máx. ${canjeCobro.max} pts`}
                    />
                    <p className="hint">10 puntos = $1. Mínimo 50. Solo múltiplos de 10.</p>
                    {canjeCobro.error && (
                      <p style={{ margin: "0.25rem 0 0", color: "var(--berry)" }}>{canjeCobro.error}</p>
                    )}
                    {canjeCobro.puntos > 0 && (
                      <p className="hint">
                        Equivale a ${canjeCobro.equivalencia.toFixed(2)}. Resta ${canjeCobro.importe.toFixed(2)}.
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="hint">Canje disponible desde 50 puntos y tickets de $5 o más.</p>
                )}
                <button
                  type="button"
                  className="btn btn--secondary btn--sm"
                  onClick={() => {
                    setClienteCobro(null);
                    setPuntosCanjeInput("");
                  }}
                >
                  Cambiar
                </button>
              </div>
            ) : (
              <>
                <div className="cliente-busqueda">
                  <input
                    className="input"
                    placeholder="Teléfono o nombre…"
                    value={busquedaCobro}
                    onChange={(e) => setBusquedaCobro(e.target.value)}
                    autoFocus={!cobroEfectivo}
                  />
                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    <input
                      className="input cliente-qr-input"
                      placeholder="Código CAFE-…"
                      value={qrCobro}
                      style={{ flex: 1, minWidth: "8rem" }}
                      onChange={(e) => {
                        const v = e.target.value;
                        setQrCobro(v);
                        const codigo = parseCodigoFidelidad(v);
                        if (codigo) resolverQrCobro(v);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") resolverQrCobro(qrCobro);
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn--primary btn--sm inline-flex items-center gap-1"
                      onClick={() => setShowQrScanner(true)}
                    >
                      <HiOutlineQrCode className="size-5 shrink-0" aria-hidden />
                      Escanear QR
                    </button>
                  </div>
                  <button
                    type="button"
                    className="btn btn--secondary btn--sm"
                    onClick={() => setShowNuevoCliente(true)}
                  >
                    + Nuevo
                  </button>
                </div>
                {buscandoCobro && <p className="hint">Buscando…</p>}
                {resultadosCobro.length > 0 && (
                  <ul className="cliente-resultados">
                    {resultadosCobro.map((c) => (
                      <li key={c.id_cliente}>
                        <button
                          type="button"
                          className="cliente-resultado-btn"
                          onClick={() => seleccionarClienteCobro(c)}
                        >
                          {c.nombre} · {c.telefono} · {c.puntos_saldo} pts
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}

            </div>
            <div className="modal-footer modal-footer--cobro" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
              {!modoParaLlevar && canUseBluetoothPrinter() && (
                <button
                  type="button"
                  className="btn btn--secondary inline-flex items-center gap-2"
                  onClick={handleReimprimirPrecuenta}
                  disabled={loading || imprimiendoPrecuenta}
                >
                  <HiOutlinePrinter className="size-5" aria-hidden />
                  {imprimiendoPrecuenta ? "Imprimiendo…" : "Reimprimir precuenta"}
                </button>
              )}
              <button type="button" className="btn btn--secondary" onClick={cerrarCobroModal} disabled={loading}>
                Cancelar
              </button>
              {!pedido?.id_cliente && (
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => iniciarConfirmacionCobro(false)}
                  disabled={botonCobroBloqueado({ loading, bloquea: cobroBloqueado }) || canjeCobro.puntos > 0}
                >
                  Cobrar sin cliente
                </button>
              )}
              {pedido?.id_cliente && (
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={async () => {
                    const nombre = clienteCobro?.nombre || pedido.cliente_nombre || "el cliente";
                    const ok = await askOperConfirm({
                      message: `¿Quitar a ${nombre} de este pedido y cobrar sin puntos?`,
                      confirmLabel: "Quitar y cobrar",
                    });
                    if (!ok) return;
                    ejecutarCobro(false, false, true);
                  }}
                  disabled={botonCobroBloqueado({ loading, bloquea: false })}
                >
                  Quitar cliente y cobrar sin puntos
                </button>
              )}
              <button
                type="button"
                className="btn btn--success"
                onClick={() => iniciarConfirmacionCobro(true)}
                disabled={botonCobroBloqueado({ loading, bloquea: cobroBloqueado }) || !clienteCobro}
              >
                {loading
                  ? "Procesando…"
                  : clienteCobro
                    ? puntosPreviewCobro > 0
                      ? `Cobrar con ${clienteCobro.nombre} y sumar ${puntosPreviewCobro} pts`
                      : `Cobrar con ${clienteCobro.nombre}`
                    : "Selecciona un cliente"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showImprimirTicketModal && (
        <div className="modal-overlay" onClick={() => setShowImprimirTicketModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h2>¿Deseas imprimir el ticket?</h2>
            <p className="hint">
              Se registrará la venta con pago{" "}
              {FORMAS_PAGO.find((f) => f.value === formaPago)?.label ?? formaPago}.
            </p>
            <div className="modal-footer" style={{ marginTop: "1rem" }}>
              <button
                type="button"
                className="btn btn--secondary"
                disabled={loading}
                onClick={() => {
                  const { conCliente } = cobroPendiente || { conCliente: false };
                  setShowImprimirTicketModal(false);
                  ejecutarCobro(conCliente, false);
                }}
              >
                No imprimir
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={loading}
                onClick={() => {
                  const { conCliente } = cobroPendiente || { conCliente: false };
                  setShowImprimirTicketModal(false);
                  ejecutarCobro(conCliente, true);
                }}
              >
                Sí, imprimir ticket
              </button>
            </div>
          </div>
        </div>
      )}

      {showQrScanner && (
        <QrScannerModal
          open={showQrScanner}
          onClose={() => setShowQrScanner(false)}
          onScan={resolverQrCobro}
        />
      )}

      {clienteQrRecienCreado && (
        <div className="modal-overlay" style={{ zIndex: 1100 }} onClick={() => setClienteQrRecienCreado(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h2>Cliente registrado</h2>
            <p>
              <strong>{clienteQrRecienCreado.nombre}</strong> ya está seleccionado para este cobro.
            </p>
            <p className="hint">Código QR de fidelidad (para futuras visitas):</p>
            <QrCodeDisplay codigo={clienteQrRecienCreado.codigo_fidelidad} size={200} />
            {puntosPreviewCobro > 0 && (
              <p className="hint" style={{ marginTop: "0.75rem" }}>
                Esta compra sumará <strong>+{puntosPreviewCobro} pts</strong> al cobrar.
              </p>
            )}
            <div className="modal-footer">
              <button type="button" className="btn btn--primary" onClick={() => setClienteQrRecienCreado(null)}>
                Continuar cobro
              </button>
            </div>
          </div>
        </div>
      )}

      {showNuevoCliente && (
        <div className="modal-overlay" onClick={() => setShowNuevoCliente(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h2>Registrar cliente</h2>
            <div className="form-row">
              <label>Nombre</label>
              <input className="input" value={nuevoNombre} onChange={(e) => setNuevoNombre(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Teléfono</label>
              <input className="input" value={nuevoTelefono} onChange={(e) => setNuevoTelefono(e.target.value)} />
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn--secondary" onClick={() => setShowNuevoCliente(false)}>
                Cancelar
              </button>
              <button type="button" className="btn btn--primary" onClick={guardarNuevoCliente}>
                Registrar y usar en cobro
              </button>
            </div>
          </div>
        </div>
      )}
      {lineaCancelar && (
        <CancelacionLineaModal
          linea={lineaCancelar}
          onClose={() => setLineaCancelar(null)}
          onOk={onCancelacionOk}
        />
      )}
      <OperationalConfirmModal
        open={Boolean(recalculoConfirm)}
        title="Confirmar nuevo total"
        message={recalculoConfirm?.message || ""}
        confirmLabel="Cobrar con el total actualizado"
        onConfirm={() => recalculoConfirm?.onConfirm?.()}
        onCancel={() => setRecalculoConfirm(null)}
      />
      <OperationalConfirmModal
        open={Boolean(operConfirm)}
        title={operConfirm?.title || "Confirmar"}
        message={operConfirm?.message || ""}
        confirmLabel={operConfirm?.confirmLabel || "Continuar"}
        cancelLabel={operConfirm?.cancelLabel || "Cancelar"}
        onConfirm={() => operConfirm?.onConfirm?.()}
        onCancel={() => operConfirm?.onCancel?.()}
      />
    </div>
  );
}
