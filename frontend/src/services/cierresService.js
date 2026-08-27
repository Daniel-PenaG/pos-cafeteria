import api from "../api/axios";

export async function getResumenCierre(fecha = null, idUsuario = null) {
  const params = {};
  if (fecha) params.fecha = fecha;
  if (idUsuario) params.id_usuario = idUsuario;
  const res = await api.get("/cierres/resumen", { params });
  return res.data;
}

export async function registrarCierre(efectivoContado, notas = "") {
  const res = await api.post("/cierres/", {
    efectivo_contado: efectivoContado,
    notas: notas || null,
  });
  return res.data;
}

export async function getCierresDia(fecha) {
  const params = fecha ? { fecha } : {};
  const res = await api.get("/cierres/", { params });
  return res.data;
}
