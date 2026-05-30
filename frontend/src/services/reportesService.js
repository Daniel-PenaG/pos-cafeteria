import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getVentasDia(fecha) {
  const res = await api.get(`/reportes/ventas-dia?fecha=${fecha}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getConsumoInsumos(fecha) {
  const res = await api.get(`/reportes/consumo-insumos?fecha=${fecha}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getResumenDashboard() {
  const res = await api.get("/reportes/resumen-dashboard", {
    headers: getAuthHeader(),
  });
  return res.data;
}
