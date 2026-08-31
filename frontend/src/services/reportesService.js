import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getProductosRanking({ periodo, fecha, anio, mes, orden = "cantidad" }) {
  const params = new URLSearchParams({ periodo, orden });
  if (fecha) params.set("fecha", fecha);
  if (anio != null) params.set("anio", String(anio));
  if (mes != null) params.set("mes", String(mes));
  const res = await api.get(`/reportes/productos-ranking?${params}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getTiemposPreparacion(fecha) {
  const res = await api.get(`/reportes/tiempos-preparacion?fecha=${fecha}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getVentasMes(anio, mes) {
  const res = await api.get(`/reportes/ventas-mes?anio=${anio}&mes=${mes}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getVentasAnio(anio) {
  const res = await api.get(`/reportes/ventas-anio?anio=${anio}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getVentasDia(fecha) {
  const res = await api.get(`/reportes/ventas-dia?fecha=${fecha}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getVentasRango(fechaInicio, fechaFin) {
  const params = new URLSearchParams({
    fecha_inicio: fechaInicio,
    fecha_fin: fechaFin,
  });
  const res = await api.get(`/reportes/ventas-rango?${params}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getVentasComparar({
  fechaInicioA,
  fechaFinA,
  fechaInicioB,
  fechaFinB,
}) {
  const params = new URLSearchParams({
    fecha_inicio_a: fechaInicioA,
    fecha_fin_a: fechaFinA,
    fecha_inicio_b: fechaInicioB,
    fecha_fin_b: fechaFinB,
  });
  const res = await api.get(`/reportes/ventas-comparar?${params}`, {
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

export async function getPromocionesVentasReporte({ periodo, fecha, anio, mes }) {
  const params = { periodo };
  if (fecha) params.fecha = fecha;
  if (anio != null) params.anio = anio;
  if (mes != null) params.mes = mes;
  const res = await api.get("/promociones/resumen", {
    params,
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getCuentasPorCajero(fecha) {
  const res = await api.get(`/reportes/cuentas-por-cajero?fecha=${fecha}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}
