import { Link, useLocation } from "react-router-dom";

const NAV = [
  { group: "Inicio", items: [{ to: "/dashboard", label: "Dashboard", icon: "◆" }] },
  {
    group: "Catálogo",
    items: [
      { to: "/categorias", label: "Categorías", icon: "▤" },
      { to: "/productos", label: "Productos", icon: "☕" },
      { to: "/insumos", label: "Insumos", icon: "◇" },
      { to: "/recetas", label: "Recetas", icon: "✦" },
    ],
  },
  {
    group: "Operación",
    items: [
      { to: "/ventas", label: "Ventas", icon: "◎" },
      { to: "/extras-venta", label: "Extras de venta", icon: "＋" },
      { to: "/compras", label: "Compras", icon: "↗" },
    ],
  },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <h1 className="sidebar__logo">Café POS</h1>
        <p className="sidebar__tagline">Gestión de cafetería</p>
      </div>

      <nav className="sidebar__nav">
        {NAV.map((section) => (
          <div key={section.group}>
            <p className="sidebar__group-label">{section.group}</p>
            {section.items.map((item) => (
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
                  {item.icon}
                </span>
                {item.label}
              </Link>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
