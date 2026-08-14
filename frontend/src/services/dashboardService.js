import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getResumenDashboard(fecha) {
  const params = fecha ? { fecha } : {};
  const res = await api.get("/reportes/resumen-dashboard", {
    params,
    headers: getAuthHeader(),
  });
  return res.data;
}
