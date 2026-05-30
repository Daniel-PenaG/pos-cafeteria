import { useState } from "react";
import api from "../api/axios";
import { useAuthStore } from "../store/authStore";
import { useNavigate } from "react-router-dom";

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
      navigate("/dashboard");
    } catch {
      alert("Credenciales incorrectas");
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
            <div className="form-row">
              <label htmlFor="user">Usuario</label>
              <input
                id="user"
                className="input"
                placeholder="Tu usuario"
                value={usuario_login}
                onChange={(e) => setUsuario(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="form-row">
              <label htmlFor="pass">Contraseña</label>
              <input
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
              className="btn btn--accent"
              style={{ width: "100%", marginTop: "0.5rem", padding: "0.75rem" }}
              disabled={loading}
            >
              {loading ? "Entrando…" : "Entrar al sistema"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
