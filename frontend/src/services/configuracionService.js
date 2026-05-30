import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getConfiguracion() {
  const res = await api.get("/configuracion/", { headers: getAuthHeader() });
  return res.data;
}

export async function updateConfiguracion(data) {
  const res = await api.put("/configuracion/", data, { headers: getAuthHeader() });
  return res.data;
}

export async function calcularPrecioSugerido(costoUnitario) {
  const res = await api.post(
    "/configuracion/calcular-precio",
    { costo_unitario: costoUnitario },
    { headers: getAuthHeader() }
  );
  return res.data;
}
