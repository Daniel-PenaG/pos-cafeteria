import api from "../api/axios";

export async function getResumenCierre(fecha = null, idUsuario = null) {
  const params = {};
  if (fecha) params.fecha = fecha;
  if (idUsuario) params.id_usuario = idUsuario;
  const res = await api.get("/cierres/resumen", { params });
  return res.data;
}

export async function registrarCierre(efectivoContado, notas = "", fecha = null) {
  const payload = {
    efectivo_contado: efectivoContado,
    notas: notas || null,
  };
  if (fecha) payload.fecha = fecha;
  const res = await api.post("/cierres/", payload);
  return res.data;
}

export async function getCierresDia(fecha) {
  const params = fecha ? { fecha } : {};
  const res = await api.get("/cierres/", { params });
  return res.data;
}
