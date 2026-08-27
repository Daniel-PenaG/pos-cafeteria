import { Link, useLocation } from "react-router-dom";
import { HiOutlineBuildingStorefront } from "react-icons/hi2";
import { useAuthStore } from "../store/authStore";
import { canAccessRoute, normalizeRole } from "../config/permissions";
import NavIcon from "./NavIcon";

const NAV = [
  {
    group: "Inicio",
    items: [{ to: "/dashboard", label: "Dashboard", roles: ["ADMIN", "CAJERO"] }],
  },
  {
    group: "Catálogo",
    items: [
      { to: "/categorias", label: "Categorías", roles: ["ADMIN"] },
      { to: "/productos", label: "Productos", roles: ["ADMIN"] },
      { to: "/insumos", label: "Insumos", roles: ["ADMIN"] },
      { to: "/recetas", label: "Recetas", roles: ["ADMIN"] },
    ],
  },
  {
    group: "Operación",
    items: [
      { to: "/ventas", label: "Ventas", roles: ["ADMIN", "CAJERO"] },
      { to: "/mesas-activas", label: "Mesas activas", roles: ["ADMIN", "CAJERO"] },
      { to: "/ventas-para-llevar", label: "Para llevar", roles: ["ADMIN", "CAJERO"] },
      { to: "/comandera", label: "Comandera", roles: ["ADMIN", "CAJERO", "COCINA"] },
      { to: "/clientes", label: "Clientes", roles: ["ADMIN", "CAJERO"] },
      { to: "/promociones", label: "Promociones", roles: ["ADMIN"] },
      { to: "/extras-venta", label: "Extras de venta", roles: ["ADMIN"] },
      { to: "/para-llevar", label: "Productos para llevar", roles: ["ADMIN"] },
      { to: "/compras", label: "Compras", roles: ["ADMIN"] },
      { to: "/gastos", label: "Gastos", roles: ["ADMIN"] },
      { to: "/cierre-caja", label: "Cierre de caja", roles: ["ADMIN", "CAJERO"] },
    ],
  },
  {
    group: "Administración",
    items: [
      { to: "/reportes", label: "Reportes", roles: ["ADMIN"] },
      { to: "/cuentas-cajero", label: "Cuentas por cajero", roles: ["ADMIN"] },
      { to: "/cierres-dia", label: "Cierres del día", roles: ["ADMIN"] },
      { to: "/usuarios", label: "Usuarios", roles: ["ADMIN"] },
    ],
  },
];

export default function Sidebar() {
  const location = useLocation();
  const rol = normalizeRole(useAuthStore((state) => state.user?.rol));
  const modulos = useAuthStore((state) => state.user?.modulos);

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-lg bg-white/15 text-white">
            <HiOutlineBuildingStorefront className="size-5" aria-hidden />
          </span>
          <div>
            <h1 className="sidebar__logo">Café POS</h1>
            <p className="sidebar__tagline">Gestión de cafetería</p>
          </div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV.map((section) => {
          const items = section.items.filter((item) =>
            canAccessRoute(rol, item.to, modulos)
          );
          if (!items.length) return null;

          return (
            <div key={section.group}>
              <p className="sidebar__group-label">{section.group}</p>
              {items.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={
                    location.pathname === item.to
                      ? "sidebar__link sidebar__link--active"
                      : "sidebar__link"
                  }
                >
                  <span className="sidebar__icon" aria-hidden>
                    <NavIcon to={item.to} className="size-[1.1rem]" />
                  </span>
                  {item.label}
                </Link>
              ))}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
