export const ROLES = {
  ADMIN: "ADMIN",
  CAJERO: "CAJERO",
  COCINA: "COCINA",
};

export const ROLE_LABELS = {
  ADMIN: "Administrador",
  CAJERO: "Cajero",
  COCINA: "Cocina",
};

/** Catálogo de módulos (sincronizado con backend/app/constants/modulos.py) */
export const MODULE_CATALOG = [
  { path: "/dashboard", label: "Dashboard", grupo: "Inicio" },
  { path: "/categorias", label: "Categorías", grupo: "Catálogo" },
  { path: "/productos", label: "Productos", grupo: "Catálogo" },
  { path: "/insumos", label: "Insumos", grupo: "Catálogo" },
  { path: "/recetas", label: "Recetas", grupo: "Catálogo" },
  { path: "/ventas", label: "Ventas", grupo: "Operación" },
  { path: "/mesas-activas", label: "Mesas activas", grupo: "Operación" },
  { path: "/ventas-para-llevar", label: "Para llevar", grupo: "Operación" },
  { path: "/comandera", label: "Comandera", grupo: "Operación" },
  { path: "/clientes", label: "Clientes", grupo: "Operación" },
  { path: "/promociones", label: "Promociones", grupo: "Operación" },
  { path: "/extras-venta", label: "Extras de venta", grupo: "Operación" },
  { path: "/para-llevar", label: "Productos para llevar", grupo: "Operación" },
  { path: "/compras", label: "Compras", grupo: "Operación" },
  { path: "/gastos", label: "Gastos", grupo: "Operación" },
  { path: "/cierre-caja", label: "Cierre de caja", grupo: "Operación" },
  { path: "/reportes", label: "Reportes", grupo: "Administración" },
  { path: "/cuentas-cajero", label: "Cuentas por cajero", grupo: "Administración" },
  { path: "/cierres-dia", label: "Cierres del día", grupo: "Administración" },
  { path: "/usuarios", label: "Usuarios", grupo: "Administración" },
  { path: "/auditoria", label: "Auditoría", grupo: "Administración" },
];

export const ALL_ROUTES = MODULE_CATALOG.map((m) => m.path);

export const ROLE_ROUTES = {
  ADMIN: ALL_ROUTES,
  CAJERO: [
    "/dashboard",
    "/ventas",
    "/mesas-activas",
    "/ventas-para-llevar",
    "/comandera",
    "/clientes",
    "/cierre-caja",
  ],
  COCINA: ["/comandera"],
};

export function normalizeRole(rol) {
  if (!rol) return "";
  const upper = String(rol).trim().toUpperCase();
  if (ROLE_ROUTES[upper]) return upper;
  const lower = String(rol).trim().toLowerCase();
  if (lower === "admin" || lower === "administrador" || lower === "cafeteria admin") {
    return ROLES.ADMIN;
  }
  if (lower === "cajero") return ROLES.CAJERO;
  if (lower === "cocina") return ROLES.COCINA;
  return upper;
}

/** Rutas efectivas: null = defaults del rol; [] = sin módulos. */
export function getEffectiveRoutes(rol, modulos) {
  const r = normalizeRole(rol);
  if (r === ROLES.ADMIN) return ALL_ROUTES;
  if (Array.isArray(modulos)) {
    return modulos.filter((p) => ALL_ROUTES.includes(p));
  }
  return ROLE_ROUTES[r] || [];
}

export function canAccessRoute(rol, path, modulos = null) {
  return getEffectiveRoutes(rol, modulos).includes(path);
}

export function getDefaultRoute(rol, modulos = null) {
  const routes = getEffectiveRoutes(rol, modulos);
  if (routes.includes("/ventas")) return "/ventas";
  if (routes.includes("/comandera")) return "/comandera";
  if (routes.includes("/dashboard")) return "/dashboard";
  return routes[0] || "/login";
}

export function isAdmin(rol) {
  return normalizeRole(rol) === ROLES.ADMIN;
}

export const ACCION_COBRAR_DESDE_COMANDERA = "COBRAR_DESDE_COMANDERA";
export const ACCION_CANCELAR_PRODUCTO_EN_COMANDA = "CANCELAR_PRODUCTO_EN_COMANDA";
export const ACCION_ABRIR_CAJA = "ABRIR_CAJA";
export const ACCION_REGISTRAR_MOVIMIENTO_CAJA = "REGISTRAR_MOVIMIENTO_CAJA";
export const ACCION_CERRAR_CAJA = "CERRAR_CAJA";
export const ACCION_REVISAR_CIERRE_CAJA = "REVISAR_CIERRE_CAJA";
export const ACCION_ANULAR_CIERRE_CAJA = "ANULAR_CIERRE_CAJA";
export const ACCION_FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS = "FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS";

const ALL_ACCIONES = [
  ACCION_COBRAR_DESDE_COMANDERA,
  ACCION_CANCELAR_PRODUCTO_EN_COMANDA,
  ACCION_ABRIR_CAJA,
  ACCION_REGISTRAR_MOVIMIENTO_CAJA,
  ACCION_CERRAR_CAJA,
  ACCION_REVISAR_CIERRE_CAJA,
  ACCION_ANULAR_CIERRE_CAJA,
  ACCION_FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS,
];

export function getEffectiveActions(rol, acciones) {
  const r = normalizeRole(rol);
  if (r === ROLES.ADMIN) return [...ALL_ACCIONES];
  return Array.isArray(acciones) ? acciones.filter((a) => ALL_ACCIONES.includes(a)) : [];
}

export function hasAction(rol, codigo, acciones = []) {
  return getEffectiveActions(rol, acciones).includes(codigo);
}

export function canCobrarDesdeComandera(user) {
  if (!user) return false;
  return hasAction(user.rol, ACCION_COBRAR_DESDE_COMANDERA, user.permisos_acciones);
}

export function canCancelarProductoEnComanda(user) {
  if (!user) return false;
  return hasAction(user.rol, ACCION_CANCELAR_PRODUCTO_EN_COMANDA, user.permisos_acciones);
}
