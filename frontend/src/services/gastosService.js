import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getGastos(fecha) {
  const params = fecha ? { fecha } : {};
  const res = await api.get("/gastos/", { params, headers: getAuthHeader() });
  return res.data;
}

export async function createGasto(data) {
  const res = await api.post("/gastos/", data, { headers: getAuthHeader() });
  return res.data;
}

export async function updateGasto(id, data) {
  const res = await api.put(`/gastos/${id}`, data, { headers: getAuthHeader() });
  return res.data;
}

export async function deleteGasto(id) {
  const res = await api.delete(`/gastos/${id}`, { headers: getAuthHeader() });
  return res.data;
}
