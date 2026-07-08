import { Link, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { canAccessRoute, normalizeRole } from "../config/permissions";

const NAV = [
  {
    group: "Inicio",
    items: [{ to: "/dashboard", label: "Dashboard", icon: "◆", roles: ["ADMIN", "CAJERO"] }],
  },
  {
    group: "Catálogo",
    items: [
      { to: "/categorias", label: "Categorías", icon: "▤", roles: ["ADMIN"] },
      { to: "/productos", label: "Productos", icon: "☕", roles: ["ADMIN"] },
      { to: "/insumos", label: "Insumos", icon: "◇", roles: ["ADMIN"] },
      { to: "/recetas", label: "Recetas", icon: "✦", roles: ["ADMIN"] },
    ],
  },
  {
    group: "Operación",
    items: [
      { to: "/ventas", label: "Ventas", icon: "◎", roles: ["ADMIN", "CAJERO"] },
      { to: "/comandera", label: "Comandera", icon: "☰", roles: ["ADMIN", "CAJERO", "COCINA"] },
      { to: "/clientes", label: "Clientes", icon: "♥", roles: ["ADMIN", "CAJERO"] },
      { to: "/promociones", label: "Promociones", icon: "％", roles: ["ADMIN"] },
      { to: "/extras-venta", label: "Extras de venta", icon: "＋", roles: ["ADMIN"] },
      { to: "/compras", label: "Compras", icon: "↗", roles: ["ADMIN"] },
    ],
  },
  {
    group: "Administración",
    items: [
      { to: "/reportes", label: "Reportes", icon: "▦", roles: ["ADMIN"] },
      { to: "/usuarios", label: "Usuarios", icon: "◉", roles: ["ADMIN"] },
    ],
  },
];

export default function Sidebar({ open = false, onClose }) {
  const location = useLocation();
  const rol = normalizeRole(useAuthStore((state) => state.user?.rol));

  return (
    <aside className={`sidebar${open ? " sidebar--open" : ""}`} aria-hidden={!open ? undefined : false}>
      <div className="sidebar__brand">
        <h1 className="sidebar__logo">Café POS</h1>
        <p className="sidebar__tagline">Gestión de cafetería</p>
      </div>

      <nav className="sidebar__nav">
        {NAV.map((section) => {
          const items = section.items.filter((item) => canAccessRoute(rol, item.to));
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
                  onClick={onClose}
                >
                  <span className="sidebar__icon" aria-hidden>
                    {item.icon}
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
