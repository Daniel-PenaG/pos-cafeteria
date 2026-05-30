import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getResumenDashboard() {
  const res = await api.get("/reportes/resumen-dashboard", {
    headers: getAuthHeader(),
  });
  return res.data;
}
