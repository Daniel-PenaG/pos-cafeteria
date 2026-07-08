import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getInsumos() {
  const res = await api.get("/catalogo/insumos", { headers: getAuthHeader() });
  return res.data;
}

export async function getInsumo(id) {
  const res = await api.get(`/catalogo/insumos/${id}`, { headers: getAuthHeader() });
  return res.data;
}

export async function createInsumo(data) {
  const res = await api.post("/catalogo/insumos", data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function updateInsumo(id, data) {
  const res = await api.put(`/catalogo/insumos/${id}`, data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function deleteInsumo(id) {
  const res = await api.delete(`/catalogo/insumos/${id}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function traspasarInsumo(id, cantidad) {
  const res = await api.post(
    `/catalogo/insumos/${id}/traspaso`,
    { cantidad },
    { headers: getAuthHeader() }
  );
  return res.data;
}
