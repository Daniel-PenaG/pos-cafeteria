import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

export default function ProtectedRoute({ children }) {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const login = useAuthStore((state) => state.login);
  const logout = useAuthStore((state) => state.logout);
  const setAuthReady = useAuthStore((state) => state.setAuthReady);

  useEffect(() => {
    let cancelled = false;

    async function validateSession() {
      if (!token) {
        if (!cancelled) setAuthReady(true);
        return;
      }

      try {
        const res = await api.get("/auth/me");
        if (!cancelled) login(token, res.data);
      } catch {
        if (!cancelled) logout();
      } finally {
        if (!cancelled) setAuthReady(true);
      }
    }

    validateSession();
    return () => {
      cancelled = true;
    };
  }, [token, login, logout, setAuthReady]);

  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center text-mocha">
        Verificando sesión…
      </div>
    );
  }

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
