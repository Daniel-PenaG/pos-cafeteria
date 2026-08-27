import { useState } from "react";
import { HiOutlineUser, HiOutlineLockClosed, HiOutlineArrowRightCircle } from "react-icons/hi2";
import api from "../api/axios";
import { useAuthStore } from "../store/authStore";
import { useNavigate } from "react-router-dom";
import { getDefaultRoute } from "../config/permissions";
import { isNativeApp } from "../services/platformService";
export default function Login() {
  const [usuario_login, setUsuario] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e?.preventDefault();
    try {
      setLoading(true);
      const res = await api.post("/auth/login", {
        usuario_login,
        password,
      });
      useAuthStore.getState().login(res.data.access_token, res.data.user);
      navigate(getDefaultRoute(res.data.user?.rol, res.data.user?.modulos));
    } catch (err) {
      let msg;
      if (!err.response) {
        if (isNativeApp()) {
          msg =
            "No se pudo conectar con el servidor. Revisa que la tablet tenga internet y que la API en Render esté activa (pos-cafeteria-api.onrender.com).";
        } else if (import.meta.env.PROD) {
          msg =
            "No se pudo conectar con el servidor. Intenta de nuevo en unos segundos o contacta al administrador.";
        } else {
          msg =
            "No se pudo conectar con el servidor. Inicia el backend en local: cd backend; .\\run-dev.ps1 (API en http://127.0.0.1:8000)";
        }
      } else {        const detail = err.response?.data?.detail;
        msg =
          typeof detail === "string"
            ? detail
            : "Credenciales incorrectas. En local usa admin / admin123";
      }
      alert(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-page__hero">
        <h1>Bienvenido</h1>
        <p>
          Administra ventas, recetas e inventario de tu cafetería desde un solo
          lugar. Caliente, fresco y siempre al día.
        </p>
      </div>

      <div className="login-page__form-wrap">
        <div className="login-card">
          <h2>Iniciar sesión</h2>
          <p>Ingresa tus credenciales para continuar</p>

          <form onSubmit={handleLogin}>
            {import.meta.env.DEV && (
              <p className="hint" style={{ marginBottom: "1rem" }}>
                Desarrollo local: usuario <strong>admin</strong>, contraseña{" "}
                <strong>admin123</strong>
              </p>
            )}
            <div className="form-row">
              <label htmlFor="user" className="flex items-center gap-1.5">
                <HiOutlineUser className="size-4 text-mocha" aria-hidden />
                Usuario
              </label>              <input
                id="user"
                className="input"
                placeholder="Tu usuario"
                value={usuario_login}
                onChange={(e) => setUsuario(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="form-row">
              <label htmlFor="pass" className="flex items-center gap-1.5">
                <HiOutlineLockClosed className="size-4 text-mocha" aria-hidden />
                Contraseña
              </label>              <input
                id="pass"
                className="input"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <button
              type="submit"
              className="btn btn--accent inline-flex w-full items-center justify-center gap-2"
              style={{ marginTop: "0.5rem", padding: "0.75rem" }}
              disabled={loading}
            >
              <HiOutlineArrowRightCircle className="size-5" aria-hidden />
              {loading ? "Entrando…" : "Entrar al sistema"}
            </button>          </form>
        </div>
      </div>
    </div>
  );
}
