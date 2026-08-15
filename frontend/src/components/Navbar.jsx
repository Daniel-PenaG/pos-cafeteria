import { HiOutlineArrowRightOnRectangle, HiOutlineUserCircle } from "react-icons/hi2";
import { useAuthStore } from "../store/authStore";
import { useNavigate } from "react-router-dom";
import { ROLE_LABELS, normalizeRole } from "../config/permissions";

export default function Navbar() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <h2 className="navbar__title">Panel de administración</h2>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        {user?.nombre && (
          <span className="navbar__user inline-flex items-center gap-1.5">
            <HiOutlineUserCircle className="size-5 text-mocha" aria-hidden />
            {user.nombre}
            {user.rol && (
              <span className="badge" style={{ marginLeft: "0.5rem" }}>
                {ROLE_LABELS[normalizeRole(user.rol)] || user.rol}
              </span>
            )}
          </span>
        )}
        <button
          type="button"
          className="btn btn--ghost btn--sm inline-flex items-center gap-1.5"
          onClick={handleLogout}
        >
          <HiOutlineArrowRightOnRectangle className="size-4" aria-hidden />
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
