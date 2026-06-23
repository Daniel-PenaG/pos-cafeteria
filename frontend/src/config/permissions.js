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

const ALL_ROUTES = [
  "/dashboard",
  "/categorias",
  "/productos",
  "/insumos",
  "/recetas",
  "/ventas",
  "/comandera",
  "/clientes",
  "/promociones",
  "/extras-venta",
  "/compras",
  "/reportes",
  "/usuarios",
];

export const ROLE_ROUTES = {
  ADMIN: ALL_ROUTES,
  CAJERO: ["/dashboard", "/ventas", "/comandera", "/clientes"],
  COCINA: ["/comandera"],
};

/** Unifica variantes legacy: admin, Admin, Administrador → ADMIN */
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

export function canAccessRoute(rol, path) {
  const r = normalizeRole(rol);
  if (!r) return false;
  const allowed = ROLE_ROUTES[r] || [];
  return allowed.includes(path);
}

export function getDefaultRoute(rol) {
  const r = normalizeRole(rol);
  if (r === ROLES.COCINA) return "/comandera";
  if (r === ROLES.CAJERO) return "/ventas";
  return "/dashboard";
}

export function isAdmin(rol) {
  return normalizeRole(rol) === ROLES.ADMIN;
}
