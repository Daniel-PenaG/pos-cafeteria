import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getPromociones() {
  const res = await api.get("/promociones/", { headers: getAuthHeader() });
  return res.data;
}

export async function getPromocionesResumen() {
  const res = await api.get("/promociones/resumen", { headers: getAuthHeader() });
  return res.data;
}

export async function getPromocionesAplicables(idProducto) {
  const res = await api.get(`/promociones/aplicables/${idProducto}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function calcularPromocion(data) {
  const res = await api.post("/promociones/calcular", data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function createPromocion(data) {
  const res = await api.post("/promociones/", data, { headers: getAuthHeader() });
  return res.data;
}

export async function updatePromocion(id, data) {
  const res = await api.put(`/promociones/${id}`, data, { headers: getAuthHeader() });
  return res.data;
}

export async function deletePromocion(id) {
  const res = await api.delete(`/promociones/${id}`, { headers: getAuthHeader() });
  return res.data;
}
