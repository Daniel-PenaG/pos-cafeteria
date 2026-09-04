import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { getProductos, getCategorias } from "../services/productosService";
import { getExtraTiposPos } from "../services/extrasVentaService";
import {
  getProductoContexto,
  invalidateProductoContextoCache,
} from "../services/productoContextoService";
import {
  getPedidosActivos,
  getPedidoMesa,
  getMesasConfig,
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
import {
  buscarClientes,
  getClientePorCodigo,
  createCliente,
  previewPuntos,
} from "../services/clientesService";
import { useAuthStore } from "../store/authStore";
import { isAdmin } from "../config/permissions";
import PageHeader from "../components/PageHeader";
import QrCodeDisplay from "../components/QrCodeDisplay";
import QrScannerModal from "../components/QrScannerModal";
import { parseCodigoFidelidad } from "../utils/fidelidadQr";
import SearchField from "../components/SearchField";
import ElapsedTimer from "../components/ElapsedTimer";
import PrinterSettings from "../components/PrinterSettings";
import { canUseBluetoothPrinter, printTicketSafely } from "../services/printerService";
import { buildCobroTicket, buildPrecuentaTicket } from "../services/escposTickets";
import { FORMAS_PAGO, esEfectivo } from "../utils/formaPago";
import { getSavedPrinter } from "../services/printerStorage";
import { formatDuration } from "../utils/formatDuration";
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
} from "react-icons/hi2";

const MESA_PARA_LLEVAR = 99;

function sumExtras(extras) {
  return extras.reduce((acc, e) => acc + Number(e.precio), 0);
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
  const [mostrarOpcionesPromo, setMostrarOpcionesPromo] = useState(false);
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

  const calcRequestRef = useRef(0);
  const contextoAbortRef = useRef(null);

  const usuario = useAuthStore((s) => s.user);
  const admin = isAdmin(usuario?.rol);
  const [searchParams] = useSearchParams();

  const lineasPedido = pedido?.lineas;
  const carrito = lineasPedido ?? [];

  const total = useMemo(
    () => (lineasPedido ?? []).reduce((acc, item) => acc + item.cantidad * item.precio_unitario, 0),
    [lineasPedido]
  );
  const subtotalNormal = pedido?.subtotal_normal;
  const descuentoPromos = pedido?.descuento_promociones;
  const resumenPromos = pedido?.resumen_promociones ?? [];

  const cobroEfectivo = esEfectivo(formaPago);
  const montoRecibidoNum = parseFloat(montoRecibido);
  const cambioCobro = useMemo(() => {
    if (!cobroEfectivo || montoRecibido === "" || isNaN(montoRecibidoNum)) return null;
    return Math.round((montoRecibidoNum - total) * 100) / 100;
  }, [cobroEfectivo, montoRecibido, montoRecibidoNum, total]);
  const montoRecibidoInsuficiente =
    cobroEfectivo &&
    montoRecibido !== "" &&
    !isNaN(montoRecibidoNum) &&
    montoRecibidoNum < total;
  const cobroEfectivoInvalido =
    cobroEfectivo &&
    (montoRecibido === "" || isNaN(montoRecibidoNum) || montoRecibidoNum < total);

  const lineasPendientesConfirmar = useMemo(
    () => (lineasPedido ?? []).filter((item) => !item.en_comanda),
    [lineasPedido]
  );

  const refrescarMesasActivas = useCallback(async () => {
    try {
      const list = await getPedidosActivos();
      const map = {};
      list.forEach((p) => {
        map[p.numero_mesa] = p;
      });
      setMesasActivas(map);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const actualizarMesasTrasAgregar = useCallback(
    (pedidoActualizado) => {
      if (modoParaLlevar || !numeroMesa) return;
      setMesasActivas((prev) => ({
        ...prev,
        [numeroMesa]: {
          ...(prev[numeroMesa] || {}),
          id_pedido: pedidoActualizado.id_pedido,
          numero_mesa: numeroMesa,
          total: pedidoActualizado.total,
          num_lineas: pedidoActualizado.lineas?.length ?? 0,
          lineas: pedidoActualizado.lineas,
        },
      }));
      refrescarMesasActivas().catch(console.error);
    },
    [modoParaLlevar, numeroMesa, refrescarMesasActivas]
  );

  const cargarMesasConfig = async () => {
    try {
      const data = await getMesasConfig();
      setMesasLista(Array.isArray(data.mesas) ? data.mesas : []);
    } catch (err) {
      console.error(err);
      setMesasLista([1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }
  };

  const handleAgregarMesa = async () => {
    try {
      setGestionMesasLoading(true);
      const data = await agregarMesa();
      setMesasLista(data.mesas);
    } catch (err) {
      const detail = err.response?.data?.detail;
      alert(typeof detail === "string" ? detail : "No se pudo agregar la mesa");
    } finally {
      setGestionMesasLoading(false);
    }
  };

  const handleQuitarMesa = async (n, e) => {
    e?.stopPropagation();
    const activa = mesasActivas[n];
    if (activa?.num_lineas > 0) {
      alert(`La mesa ${n} tiene un pedido abierto. Ciérrala antes de quitarla.`);
      return;
    }
    if (!window.confirm(`¿Quitar la mesa ${n}?`)) return;
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
      alert(typeof detail === "string" ? detail : "No se pudo quitar la mesa");
    } finally {
      setGestionMesasLoading(false);
    }
  };

  const cargarPedidoMesa = useCallback(async (mesa, paraLlevar = modoParaLlevar) => {
    if (!usuario?.id_usuario) return;
    try {
      const p = await getPedidoMesa(mesa, usuario.id_usuario, paraLlevar);
      setPedido(p);
      setCantidadEdit({});
      if (!paraLlevar) {
        refrescarMesasActivas().catch(console.error);
      }
    } catch (err) {
      console.error(err);
      alert(paraLlevar ? "Error al cargar pedido para llevar" : "Error al cargar pedido de la mesa");
    }
  }, [modoParaLlevar, usuario, refrescarMesasActivas]);

  const seleccionarMesa = useCallback(async (n) => {
    setNumeroMesa(n);
    await cargarPedidoMesa(n);
  }, [cargarPedidoMesa]);

  useEffect(() => {
    const load = async () => {
      try {
        const [prods, cats, tipos] = await Promise.all([
          getProductos(),
          getCategorias(),
          getExtraTiposPos(),
        ]);
        const activos = prods.filter((p) => p.activo !== false);
        setProductos(activos);
        invalidateProductoContextoCache();
        setCategorias(
          [...cats].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
        );
        setTiposPosLabels(
          Object.fromEntries(tipos.map((t) => [t.codigo, t.etiqueta]))
        );
      } catch (err) {
        console.error(err);
        alert("Error al cargar productos");
      }
    };
    load();
    cargarMesasConfig();
    refrescarMesasActivas();
  }, [modoParaLlevar, refrescarMesasActivas]);

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
    if (!showCobroModal || total <= 0) {
      setPuntosPreviewCobro(0);
      return;
    }
    previewPuntos(total)
      .then((r) => setPuntosPreviewCobro(r.puntos_a_ganar))
      .catch(() => setPuntosPreviewCobro(0));
  }, [showCobroModal, total]);

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
      alert("Código QR no válido. Debe ser CAFE- seguido de 6 caracteres.");
      return;
    }
    try {
      const cliente = await getClientePorCodigo(c);
      seleccionarClienteCobro(cliente);
      setQrCobro("");
      setShowQrScanner(false);
    } catch (err) {
      alert(err.response?.data?.detail || "Cliente no encontrado");
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
      alert(err.response?.data?.detail || "Error al registrar cliente");
    }
  };

  const abrirCobroModal = () => {
    setClienteCobro(null);
    setBusquedaCobro("");
    setResultadosCobro([]);
    setQrCobro("");
    setMontoRecibido("");
    setFormaPago("EFECTIVO");
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
      alert(`Precuenta: ${printResult.message || "no se pudo imprimir"}`);
    }
  };

  const handleCerrarCuenta = async () => {
    if (!pedido?.id_pedido || carrito.length === 0) return;
    if (imprimiendoPrecuenta || loading || showCobroModal) return;

    if (lineasPendientesConfirmar.length > 0) {
      if (modoParaLlevar) {
        const enviar = window.confirm(
          `Hay ${lineasPendientesConfirmar.length} producto(s) sin enviar a comandera.\n\n¿Enviar a comandera ahora?`
        );
        if (!enviar) return;
        const ok = await confirmarPedidoComanda();
        if (!ok) return;
      } else {
        alert("Confirma el pedido en comanda antes de cerrar la cuenta.");
        return;
      }
    }

    if (modoParaLlevar) {
      abrirCobroModal();
      return;
    }

    setPrecuentaImpresa(false);
    if (canUseBluetoothPrinter()) {
      const printResult = await imprimirPrecuenta();
      if (!printResult.skipped && !printResult.ok) {
        alert(`Precuenta: ${printResult.message || "no se pudo imprimir"}`);
      }
    }

    abrirCobroModal();
  };

  const cerrarCobroModal = () => {
    setShowCobroModal(false);
    setClienteCobro(null);
    setBusquedaCobro("");
    setResultadosCobro([]);
    setQrCobro("");
    setMontoRecibido("");
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
    if (!productoModal) return undefined;
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
  }, [productoModal, promoModo, extrasSeleccionados, cantidadModal, recalcularPromoModal]);

  const abrirModalProducto = async (producto, opts = {}) => {
    if (!numeroMesa) {
      alert(modoParaLlevar ? "Espera a que cargue el pedido" : "Primero selecciona el número de mesa");
      return;
    }
    if (contextoAbortRef.current) {
      contextoAbortRef.current.abort();
    }
    setProductoModal(producto);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
    setPromosDisponibles([]);
    setPromoModo(opts.promoModo ?? "auto");
    setMostrarOpcionesPromo(false);
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
      alert("Error al cargar opciones del producto");
      setProductoModal(null);
    } finally {
      setCargandoExtras(false);
    }
  };

  const handleProductoClick = async (producto) => {
    if (!numeroMesa) {
      alert(modoParaLlevar ? "Espera a que cargue el pedido" : "Primero selecciona el número de mesa");
      return;
    }
    if (!usuario?.id_usuario) return;

    if (contextoAbortRef.current) {
      contextoAbortRef.current.abort();
    }
    const ac = new AbortController();
    contextoAbortRef.current = ac;

    setProductoModal(producto);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
    setPromosDisponibles([]);
    setPromoModo("auto");
    setMostrarOpcionesPromo(false);
    setCalculoPromo(null);
    setCalculoInicialModal(null);
    setCantidadModal("1");
    setComentarioModal("");
    setCargandoExtras(true);

    try {
      const ctx = await getProductoContexto(producto.id_producto, { signal: ac.signal });
      if (ac.signal.aborted) return;

      const paquetes = ctx.paquetes ?? [];
      const promos = ctx.promociones ?? [];

      if (paquetes.length > 0) {
        setProductoModal(null);
        setPromoConfirm({ kind: "combo", combo: paquetes[0], producto });
        return;
      }

      if (promos.length > 0) {
        setProductoModal(null);
        setPromoConfirm({ kind: "promo", promo: promos[0], producto });
        return;
      }

      setExtrasModal(ctx.extras ?? []);
      setPromosDisponibles(ctx.promociones ?? []);
      setCalculoInicialModal(ctx.calculo_inicial ?? null);
      if (ctx.calculo_inicial) {
        setCalculoPromo(ctx.calculo_inicial);
      }
    } catch (err) {
      if (err?.code === "ERR_CANCELED" || ac.signal.aborted) return;
      console.error("Contexto producto:", err.response?.status, err.response?.data?.detail);
      setProductoModal(null);
      alert("Error al cargar opciones del producto");
    } finally {
      if (!ac.signal.aborted) {
        setCargandoExtras(false);
      }
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
      try {
        const pedidoActualizado = await agregarComboPedido(
          numeroMesa,
          usuario.id_usuario,
          { id_promocion: combo.id_promocion, cantidad: 1, enviar_comanda: false },
          modoParaLlevar
        );
        setPedido(pedidoActualizado);
        setCantidadEdit({});
        actualizarMesasTrasAgregar(pedidoActualizado);
      } catch (err) {
        alert(err.response?.data?.detail || "Error al agregar combo");
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
      alert("Indica una cantidad mayor a 0");
      return;
    }
    if (!calculoPromo.margen_ok) {
      alert(calculoPromo.mensaje || "La promoción no cumple el margen mínimo");
      return;
    }

    try {
      setGuardandoLinea(true);
      const pedidoActualizado = await agregarLineaPedido(numeroMesa, usuario.id_usuario, {
        id_producto: productoModal.id_producto,
        cantidad: cant,
        precio_unitario: Number(calculoPromo.precio_unitario),
        precio_original: Number(calculoPromo.precio_original_unitario),
        id_promocion: calculoPromo.id_promocion,
        extras: extrasSeleccionados,
        enviar_comanda: false,
        comentario: comentarioModal.trim() || null,
      }, modoParaLlevar);
      setPedido(pedidoActualizado);
      setCantidadEdit({});
      actualizarMesasTrasAgregar(pedidoActualizado);
    } catch (err) {
      alert(err.response?.data?.detail || "Error al agregar al pedido");
      return;
    } finally {
      setGuardandoLinea(false);
    }

    setProductoModal(null);
    setExtrasSeleccionados([]);
    setExtrasModal([]);
    setPromosDisponibles([]);
    setPromoModo("auto");
    setMostrarOpcionesPromo(false);
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

    try {
      await actualizarLineaPedido(idDetalle, { cantidad: cant });
      await cargarPedidoMesa(numeroMesa, modoParaLlevar);
      return true;
    } catch (err) {
      alert(err.response?.data?.detail || "Error al actualizar cantidad");
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
      alert("La cantidad debe ser un número mayor a 0");
      return;
    }

    await cambiarCantidad(idDetalle, cant);
  };

  const eliminarDelCarrito = async (idDetalle) => {
    if (!numeroMesa) return;
    try {
      await eliminarLineaPedido(idDetalle);
      await cargarPedidoMesa(numeroMesa, modoParaLlevar);
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar línea");
    }
  };

  const confirmarPedidoComanda = async () => {
    if (!pedido?.id_pedido) return false;
    if (lineasPendientesConfirmar.length === 0) {
      alert("No hay productos pendientes de confirmar");
      return false;
    }
    try {
      setLoading(true);
      await confirmarComandaPedido(pedido.id_pedido);
      await cargarPedidoMesa(numeroMesa, modoParaLlevar);
      alert(
        modoParaLlevar
          ? "Pedido enviado a comandera"
          : "Pedido confirmado y enviado a comanda"
      );
      return true;
    } catch (err) {
      alert(err.response?.data?.detail || "Error al confirmar pedido");
      return false;
    } finally {
      setLoading(false);
    }
  };

  const iniciarConfirmacionCobro = (conCliente) => {
    if (cobroEfectivoInvalido) {
      alert(`Indica cuánto paga el cliente (mínimo $${total.toFixed(2)})`);
      return;
    }
    if (modoParaLlevar && canUseBluetoothPrinter()) {
      setCobroPendiente({ conCliente });
      setShowImprimirTicketModal(true);
      return;
    }
    ejecutarCobro(conCliente, false);
  };

  const ejecutarCobro = async (conCliente, imprimirTicket = false) => {
    if (!usuario?.id_usuario || !pedido?.id_pedido) return;

    if (cobroEfectivoInvalido) {
      alert(`Indica cuánto paga el cliente (mínimo $${total.toFixed(2)})`);
      return;
    }

    const pagaCon = cobroEfectivo ? montoRecibidoNum : null;
    const cambio = cobroEfectivo ? cambioCobro : null;

    try {
      setLoading(true);
      const pedidoParaTicket = pedido;
      const res = await cobrarPedido(pedido.id_pedido, {
        id_usuario: usuario.id_usuario,
        forma_pago: formaPago,
        id_cliente: conCliente && clienteCobro ? clienteCobro.id_cliente : null,
      });

      let printResult = { skipped: true };
      if (modoParaLlevar && imprimirTicket) {
        printResult = await printTicketSafely(buildCobroTicket, {
          venta: res,
          pedido: pedidoParaTicket,
          usuario,
          clienteNombre: conCliente && clienteCobro ? clienteCobro.nombre : null,
          montoRecibido: pagaCon,
          cambio,
        });
      }

      let msg = modoParaLlevar
        ? `Venta para llevar — Folio: ${res.id_venta}\nTotal: $${Number(res.total).toFixed(2)}`
        : `Cuenta cerrada. Mesa ${res.numero_mesa} — Folio: ${res.id_venta}\nTotal: $${Number(res.total).toFixed(2)}`;
      if (!modoParaLlevar && pedidoParaTicket?.fecha_apertura) {
        const segundos = Math.floor(
          (Date.now() - new Date(pedidoParaTicket.fecha_apertura).getTime()) / 1000
        );
        if (segundos >= 0) {
          msg += `\n\nTiempo en mesa: ${formatDuration(segundos)}`;
        }
      }
      if (cobroEfectivo && pagaCon != null && cambio != null) {
        msg += `\n\nPaga con: $${pagaCon.toFixed(2)}\nCambio: $${cambio.toFixed(2)}`;
      }
      if (res.advertencias_stock?.length) {
        msg += `\n\n⚠ Avisos de inventario (la venta se completó):\n${res.advertencias_stock.join("\n")}`;
      }
      if (res.puntos_generados > 0) {
        msg += `\n\n+${res.puntos_generados} pts → ${res.cliente_nombre}\nNuevo saldo: ${res.cliente_puntos_saldo} pts`;
      }
      if (!printResult.skipped && !printResult.ok) {
        msg += `\n\n⚠ Impresión: ${printResult.message}`;
      } else if (!printResult.skipped && printResult.ok) {
        msg += "\n\nTicket impreso.";
      }
      alert(msg);
      cerrarCobroModal();
      setShowImprimirTicketModal(false);
      setCobroPendiente(null);
      if (modoParaLlevar) {
        setPedido(null);
        await cargarPedidoMesa(MESA_PARA_LLEVAR, true);
      } else {
        const mesaCobrada = numeroMesa;
        setPedido(null);
        setNumeroMesa(null);
        setMesasActivas((prev) => {
          const next = { ...prev };
          if (mesaCobrada) delete next[mesaCobrada];
          return next;
        });
        await refrescarMesasActivas();
      }
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Error al cobrar");
    } finally {
      setLoading(false);
    }
  };

  const precioPreview = calculoPromo ? Number(calculoPromo.precio_unitario) : 0;

  const ventasHabilitadas = Boolean(numeroMesa);

  return (
    <div className="page page--ventas">
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
          <div className="ventas-catalogo">
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
                            <button
                              key={p.id_producto}
                              type="button"
                              className="ventas-producto-item"
                              onClick={() => handleProductoClick(p)}
                              disabled={!ventasHabilitadas}
                            >
                              <span className="ventas-producto-item__main">
                                <span className="ventas-producto-item__dot" aria-hidden />
                                <span className="ventas-producto-item__nombre">{p.nombre}</span>
                              </span>
                              <span className="ventas-producto-item__precio">
                                ${Number(p.precio_venta).toFixed(2)}
                              </span>
                            </button>
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

        <aside className="cart-panel">
          <h2 className="flex items-center gap-2">
            {modoParaLlevar ? (
              <HiOutlineShoppingBag className="size-5 text-olive shrink-0" aria-hidden />
            ) : (
              <HiOutlineShoppingCart className="size-5 text-olive shrink-0" aria-hidden />
            )}
            {modoParaLlevar
              ? "Pedido para llevar"
              : `Pedido ${numeroMesa ? `(Mesa ${numeroMesa})` : ""}`}
          </h2>
          {carrito.length === 0 ? (
            <p className="empty-state">Sin productos en el pedido</p>
          ) : (
            <div className="cart-panel__items">
              {carrito.map((item) => (
                <div key={item.id_detalle_pedido} className="cart-item">
                  <div style={{ flex: 1 }}>
                    <strong>{item.nombre_producto}</strong>
                    {item.nombre_promocion && (
                      <span className="badge" style={{ marginLeft: "0.35rem" }}>
                        {item.nombre_promocion}
                      </span>
                    )}
                    {!item.en_comanda && !modoParaLlevar && (
                      <span className="badge badge--pending" style={{ marginLeft: "0.35rem" }}>
                        sin confirmar
                      </span>
                    )}
                    {item.cantidad_pendiente > 0 && item.en_comanda && (
                      <span className="badge badge--kitchen" style={{ marginLeft: "0.35rem" }}>
                        en comanda
                      </span>
                    )}
                    {item.en_comanda && item.cantidad_pendiente > 0 && item.fecha_envio_comanda && (
                      <span style={{ marginLeft: "0.35rem" }}>
                        <ElapsedTimer since={item.fecha_envio_comanda} />
                      </span>
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
                    {item.comentario && (
                      <p className="cart-item__comentario">📝 {item.comentario}</p>
                    )}
                    <div className="hint" style={{ marginTop: "0.25rem" }}>
                      {(item.descuento_unitario ?? 0) > 0 ? (
                        <>
                          <s>${Number(item.precio_original).toFixed(2)}</s> → $
                          {Number(item.precio_unitario).toFixed(2)} c/u
                        </>
                      ) : (
                        <>${Number(item.precio_unitario).toFixed(2)} c/u</>
                      )}
                    </div>
                  </div>
                  <input
                    type="number"
                    min="1"
                    value={
                      cantidadEdit[item.id_detalle_pedido] ?? item.cantidad
                    }
                    onChange={(e) =>
                      onCantidadLineaChange(item.id_detalle_pedido, e.target.value)
                    }
                    onFocus={(e) => e.target.select()}
                    onBlur={() => confirmarCantidadLinea(item.id_detalle_pedido)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") e.currentTarget.blur();
                    }}
                    style={{ width: 56 }}
                    className="input"
                  />
                  <span style={{ minWidth: 72, fontWeight: 600 }}>
                    ${(item.cantidad * item.precio_unitario).toFixed(2)}
                  </span>
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={() => eliminarDelCarrito(item.id_detalle_pedido)}
                    aria-label="Quitar"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="cart-panel__footer">
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
          <div className="cart-total">Total: ${total.toFixed(2)}</div>
          {!modoParaLlevar && (
            <button
              type="button"
              className="btn btn--accent inline-flex w-full items-center justify-center gap-2"
              style={{ marginTop: "0.75rem", padding: "0.75rem" }}
              onClick={confirmarPedidoComanda}
              disabled={
                loading ||
                carrito.length === 0 ||
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
              style={{ marginTop: "0.75rem", padding: "0.75rem" }}
              onClick={confirmarPedidoComanda}
              disabled={loading || carrito.length === 0 || !numeroMesa}
            >
              <HiOutlineCheckBadge className="size-5 shrink-0" aria-hidden />
              Confirmar pedido / Enviar a comandera ({lineasPendientesConfirmar.length})
            </button>
          )}
          <button
            type="button"
            className="btn btn--success inline-flex w-full items-center justify-center gap-2"
            style={{ marginTop: "0.75rem", padding: "0.75rem" }}
            onClick={handleCerrarCuenta}
            disabled={loading || imprimiendoPrecuenta || showCobroModal || carrito.length === 0 || !numeroMesa}
          >
            <HiOutlineBanknotes className="size-5 shrink-0" aria-hidden />
            {modoParaLlevar ? "Cobrar para llevar" : "Cerrar cuenta / Cobrar"}
          </button>
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
                {calculoPromo.descuento_unitario > 0 && (
                  <> · -${Number(calculoPromo.descuento_unitario).toFixed(2)} c/u</>
                )}
              </div>
            )}

            {!cargandoExtras && promosDisponibles.length > 0 && (
              <div style={{ marginBottom: "1rem" }}>
                {!mostrarOpcionesPromo ? (
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => setMostrarOpcionesPromo(true)}
                  >
                    Cambiar promoción
                  </button>
                ) : (
                  <>
                    <label className="hint">Promoción</label>
                    <select
                      className="select"
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
                      <option value="none">Sin promoción</option>
                      {promosDisponibles.map((p) => (
                        <option key={p.id_promocion} value={p.id_promocion}>
                          {p.nombre} ({p.tipo === "PORCENTAJE" ? `${p.valor}%` : p.tipo})
                        </option>
                      ))}
                    </select>
                  </>
                )}
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
                {calculoPromo.descuento_unitario > 0 ? (
                  <>
                    <s>${Number(calculoPromo.precio_original_unitario).toFixed(2)}</s>{" "}
                    <strong>${precioPreview.toFixed(2)}</strong> c/u
                    {calculoPromo.margen_porcentaje != null && (
                      <span className="hint"> · Margen {calculoPromo.margen_porcentaje}%</span>
                    )}
                    {!calculoPromo.margen_ok && (
                      <p style={{ color: "var(--color-danger, #c0392b)" }}>
                        {calculoPromo.mensaje}
                      </p>
                    )}
                  </>
                ) : (
                  <>Precio unitario: ${precioPreview.toFixed(2)}</>
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
          <div className="modal-box modal-box--wide" onClick={(e) => e.stopPropagation()}>
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

            {formaPago === "TRANSFERENCIA" && (
              <p className="hint panel-muted" style={{ marginBottom: "1rem" }}>
                Pago por <strong>Transferencia</strong>. No se solicita importe recibido ni cambio.
              </p>
            )}
            {formaPago === "TARJETA" && (
              <p className="hint panel-muted" style={{ marginBottom: "1rem" }}>
                Pago con <strong>Terminal</strong>. No se solicita importe recibido ni cambio.
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
                    placeholder={`Mín. $${total.toFixed(2)}`}
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
                        Falta ${(total - montoRecibidoNum).toFixed(2)} para cubrir el total
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
                <button
                  type="button"
                  className="btn btn--secondary btn--sm"
                  onClick={() => setClienteCobro(null)}
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

            <div className="modal-footer" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
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
              <button type="button" className="btn btn--secondary" onClick={cerrarCobroModal} disabled={loading || imprimiendoPrecuenta}>
                Cancelar
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => iniciarConfirmacionCobro(false)}
                disabled={loading || cobroEfectivoInvalido}
              >
                Cobrar sin cliente
              </button>
              <button
                type="button"
                className="btn btn--success"
                onClick={() => iniciarConfirmacionCobro(true)}
                disabled={loading || !clienteCobro || cobroEfectivoInvalido}
              >
                {loading
                  ? "Procesando…"
                  : clienteCobro
                    ? puntosPreviewCobro > 0
                      ? `Cobrar y sumar ${puntosPreviewCobro} pts`
                      : "Cobrar con cliente"
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
    </div>
  );
}
