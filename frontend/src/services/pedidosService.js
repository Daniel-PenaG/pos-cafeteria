import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getPedidosActivos() {
  const res = await api.get("/pedidos/activos", { headers: getAuthHeader() });
  return res.data;
}

export async function getMesasConfig() {
  const res = await api.get("/pedidos/mesas", { headers: getAuthHeader() });
  return res.data;
}

export async function agregarMesa(numero = null) {
  const body = numero != null ? { numero } : {};
  const res = await api.post("/pedidos/mesas", body, { headers: getAuthHeader() });
  return res.data;
}

export async function quitarMesa(numero) {
  const res = await api.delete(`/pedidos/mesas/${numero}`, { headers: getAuthHeader() });
  return res.data;
}

export async function getPedidoMesa(numeroMesa, idUsuario, paraLlevar = false) {
  const res = await api.get(`/pedidos/mesa/${numeroMesa}`, {
    params: { id_usuario: idUsuario, para_llevar: paraLlevar },
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function agregarLineaPedido(numeroMesa, idUsuario, data, paraLlevar = false) {
  const res = await api.post(`/pedidos/mesa/${numeroMesa}/lineas`, data, {
    params: { id_usuario: idUsuario, para_llevar: paraLlevar },
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function actualizarLineaPedido(idDetalle, data) {
  const res = await api.patch(`/pedidos/lineas/${idDetalle}`, data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function eliminarLineaPedido(idDetalle) {
  const res = await api.delete(`/pedidos/lineas/${idDetalle}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function asignarClientePedido(idPedido, idCliente) {
  const res = await api.put(
    `/pedidos/${idPedido}/cliente`,
    { id_cliente: idCliente },
    { headers: getAuthHeader() }
  );
  return res.data;
}

export async function confirmarComandaPedido(idPedido) {
  const res = await api.post(`/pedidos/${idPedido}/confirmar-comanda`, null, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function cobrarPedido(idPedido, data) {
  const res = await api.post(`/pedidos/${idPedido}/cobrar`, data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getComandaPendientes() {
  const res = await api.get("/comandera/pendientes", { headers: getAuthHeader() });
  return res.data;
}

export async function marcarLineaListo(idDetalle, cantidad = 1) {
  const res = await api.post(
    `/comandera/lineas/${idDetalle}/listo`,
    { cantidad },
    { headers: getAuthHeader() }
  );
  return res.data;
}
