import { useAuthStore } from "../store/authStore";
import { useNavigate } from "react-router-dom";

export default function Navbar() {
  const user = useAuthStore((state) => state.user);
  const clearToken = useAuthStore((state) => state.clearToken);
  const navigate = useNavigate();

  const handleLogout = () => {
    clearToken();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <h2 className="navbar__title">Panel de administración</h2>
      <div style={{ display: "flex", alignItems: "center" }}>
        {user?.nombre && (
          <span className="navbar__user">{user.nombre}</span>
        )}
        <button type="button" className="btn btn--ghost btn--sm" onClick={handleLogout}>
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
