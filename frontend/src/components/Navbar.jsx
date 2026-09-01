import { forwardRef } from "react";
import {
  HiOutlineArrowRightOnRectangle,
  HiOutlineBars3,
  HiOutlineUserCircle,
} from "react-icons/hi2";
import { useAuthStore } from "../store/authStore";
import { useNavigate } from "react-router-dom";
import { ROLE_LABELS, normalizeRole } from "../config/permissions";
import { SIDEBAR_ID } from "./Sidebar";

const Navbar = forwardRef(function Navbar({ onMenuOpen, menuExpanded = false }, menuBtnRef) {
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
          ref={menuBtnRef}
          type="button"
          className="navbar__menu-btn"
          aria-label="Abrir menú"
          aria-expanded={menuExpanded}
          aria-controls={SIDEBAR_ID}
          onClick={onMenuOpen}
        >
          <HiOutlineBars3 className="size-6" aria-hidden />
        </button>
        <h2 className="navbar__title">
          <span className="navbar__title-full">Panel de administración</span>
          <span className="navbar__title-short">Coffe Song</span>
        </h2>
      </div>
      <div className="navbar__actions">
        {user?.nombre && (
          <span className="navbar__user inline-flex items-center gap-1.5">
            <HiOutlineUserCircle className="size-5 text-mocha" aria-hidden />
            <span className="navbar__user-name">{user.nombre}</span>
            {user.rol && (
              <span className="badge navbar__user-badge">
                {ROLE_LABELS[normalizeRole(user.rol)] || user.rol}
              </span>
            )}
          </span>
        )}
        <button
          type="button"
          className="btn btn--ghost btn--sm inline-flex items-center gap-1.5 navbar__logout"
          onClick={handleLogout}
        >
          <HiOutlineArrowRightOnRectangle className="size-4" aria-hidden />
          <span className="navbar__logout-label">Cerrar sesión</span>
        </button>
      </div>
    </header>
  );
});

export default Navbar;
