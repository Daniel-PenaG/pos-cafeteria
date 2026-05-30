import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function crearCompra(data) {
  const res = await api.post("/compras/", data, { headers: getAuthHeader() });
  return res.data;
}

export async function getCompras() {
  const res = await api.get("/compras/", { headers: getAuthHeader() });
  return res.data;
}

export async function getCompra(id) {
  const res = await api.get(`/compras/${id}`, { headers: getAuthHeader() });
  return res.data;
}
