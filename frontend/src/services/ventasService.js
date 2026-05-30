import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getExtrasVenta(idProducto) {
  const res = await api.get(`/ventas/extras?id_producto=${idProducto}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function crearVenta(data) {
  const res = await api.post("/ventas/", data, { headers: getAuthHeader() });
  return res.data;
}

export async function getVentas() {
  const res = await api.get("/ventas/", { headers: getAuthHeader() });
  return res.data;
}

export async function getVenta(id) {
  const res = await api.get(`/ventas/${id}`, { headers: getAuthHeader() });
  return res.data;
}
