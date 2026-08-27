import { Navigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { canAccessRoute, getDefaultRoute } from "../config/permissions";

export default function RoleRoute({ path, children }) {
  const user = useAuthStore((state) => state.user);

  if (!canAccessRoute(user?.rol, path, user?.modulos)) {
    return <Navigate to={getDefaultRoute(user?.rol, user?.modulos)} replace />;
  }

  return children;
}
