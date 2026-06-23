import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getClientes() {
  const res = await api.get("/clientes/", { headers: getAuthHeader() });
  return res.data;
}

export async function getCliente(id) {
  const res = await api.get(`/clientes/${id}`, { headers: getAuthHeader() });
  return res.data;
}

export async function buscarClientes(q) {
  const res = await api.get("/clientes/buscar", {
    params: { q },
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getClientePorCodigo(codigo) {
  const res = await api.get(`/clientes/codigo/${encodeURIComponent(codigo)}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function createCliente(data) {
  const res = await api.post("/clientes/", data, { headers: getAuthHeader() });
  return res.data;
}

export async function updateCliente(id, data) {
  const res = await api.put(`/clientes/${id}`, data, { headers: getAuthHeader() });
  return res.data;
}

export async function ajustarPuntos(id, data) {
  const res = await api.post(`/clientes/${id}/ajustar-puntos`, data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getFidelidadConfig() {
  const res = await api.get("/clientes/fidelidad/config", { headers: getAuthHeader() });
  return res.data;
}

export async function updateFidelidadConfig(data) {
  const res = await api.put("/clientes/fidelidad/config", data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function previewPuntos(total) {
  const res = await api.get("/clientes/fidelidad/preview", {
    params: { total },
    headers: getAuthHeader(),
  });
  return res.data;
}

export function qrUrl(codigo) {
  return `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(codigo)}`;
}
