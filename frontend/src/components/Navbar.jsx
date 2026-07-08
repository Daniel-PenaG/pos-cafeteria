import { useAuthStore } from "../store/authStore";
import { useNavigate } from "react-router-dom";
import { ROLE_LABELS, normalizeRole } from "../config/permissions";

export default function Navbar({ onMenuClick }) {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <div className="navbar__start">
        <button
          type="button"
          className="navbar__menu-btn"
          aria-label="Abrir menú"
          onClick={onMenuClick}
        >
          ☰
        </button>
        <h2 className="navbar__title">Panel de administración</h2>
      </div>
      <div className="navbar__actions">
        {user?.nombre && (
          <span className="navbar__user">
            <span className="navbar__user-name">{user.nombre}</span>
            {user.rol && (
              <span className="badge navbar__role">
                {ROLE_LABELS[normalizeRole(user.rol)] || user.rol}
              </span>
            )}
          </span>
        )}
        <button type="button" className="btn btn--ghost btn--sm" onClick={handleLogout}>
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
