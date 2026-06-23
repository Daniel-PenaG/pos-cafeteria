import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getUsuarios() {
  const res = await api.get("/usuarios/", { headers: getAuthHeader() });
  return res.data;
}

export async function getPerfiles() {
  const res = await api.get("/usuarios/perfiles", { headers: getAuthHeader() });
  return res.data;
}

export async function createUsuario(data) {
  const res = await api.post("/usuarios/", data, { headers: getAuthHeader() });
  return res.data;
}

export async function updateUsuario(id, data) {
  const res = await api.put(`/usuarios/${id}`, data, { headers: getAuthHeader() });
  return res.data;
}

export async function deleteUsuario(id) {
  const res = await api.delete(`/usuarios/${id}`, { headers: getAuthHeader() });
  return res.data;
}
