import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getCategorias() {
  const res = await api.get("/catalogo/categorias", { headers: getAuthHeader() });
  return res.data;
}

export async function getCategoria(id) {
  const res = await api.get(`/catalogo/categorias/${id}`, { headers: getAuthHeader() });
  return res.data;
}

export async function createCategoria(data) {
  const res = await api.post("/catalogo/categorias", data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function updateCategoria(id, data) {
  const res = await api.put(`/catalogo/categorias/${id}`, data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function deleteCategoria(id) {
  const res = await api.delete(`/catalogo/categorias/${id}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}
