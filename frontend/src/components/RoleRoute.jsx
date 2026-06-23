import { Navigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { canAccessRoute, getDefaultRoute } from "../config/permissions";

export default function RoleRoute({ path, children }) {
  const user = useAuthStore((state) => state.user);

  if (!canAccessRoute(user?.rol, path)) {
    return <Navigate to={getDefaultRoute(user?.rol)} replace />;
  }

  return children;
}
