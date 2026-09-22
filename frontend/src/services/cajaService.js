import api from "../api/axios";

export async function getTerminalesCaja() {
  const res = await api.get("/caja/terminales");
  return res.data;
}

export async function getMiSesionCaja() {
  const res = await api.get("/caja/sesion");
  return res.data;
}

export async function abrirCaja(payload) {
  const res = await api.post("/caja/abrir", payload);
  return res.data;
}

export async function registrarMovimientoCaja(payload) {
  const res = await api.post("/caja/movimientos", payload);
  return res.data;
}

export async function iniciarArqueoCaja() {
  const res = await api.post("/caja/arqueo");
  return res.data;
}

export async function cerrarCaja(payload) {
  const res = await api.post("/caja/cerrar", payload);
  return res.data;
}

export async function listarSesionesCaja(params = {}) {
  const res = await api.get("/caja/sesiones", { params });
  return res.data;
}

export async function getSesionCaja(idSesion) {
  const res = await api.get(`/caja/sesiones/${idSesion}`);
  return res.data;
}

export async function revisarSesionCaja(idSesion) {
  const res = await api.post(`/caja/sesiones/${idSesion}/revisar`);
  return res.data;
}

export async function anularSesionCaja(idSesion, motivo) {
  const res = await api.post(`/caja/sesiones/${idSesion}/anular`, { motivo });
  return res.data;
}
