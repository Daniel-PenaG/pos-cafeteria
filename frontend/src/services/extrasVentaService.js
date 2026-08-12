import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getExtrasCatalogo() {
  const res = await api.get("/extras-venta/", { headers: getAuthHeader() });
  return res.data;
}

export async function getExtraTiposPos() {
  const res = await api.get("/extras-venta/tipos", { headers: getAuthHeader() });
  return res.data;
}

export async function createExtraTipoPos(etiqueta) {
  const res = await api.post(
    "/extras-venta/tipos",
    { etiqueta },
    { headers: getAuthHeader() }
  );
  return res.data;
}

export async function getInsumosImportables() {
  const res = await api.get("/extras-venta/insumos-importables", {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function createExtra(data) {
  const res = await api.post("/extras-venta/", data, { headers: getAuthHeader() });
  return res.data;
}

export async function createExtraDesdeInsumo(idInsumo, data = {}) {
  const res = await api.post(`/extras-venta/desde-insumo/${idInsumo}`, data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function updateExtra(id, data) {
  const res = await api.put(`/extras-venta/${id}`, data, { headers: getAuthHeader() });
  return res.data;
}

export async function deleteExtra(id) {
  const res = await api.delete(`/extras-venta/${id}`, { headers: getAuthHeader() });
  return res.data;
}

export async function getCategoriaExtrasConfig(idCategoria) {
  const res = await api.get(`/extras-venta/categorias/${idCategoria}/config`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function saveCategoriaExtrasConfig(idCategoria, idsExtras) {
  const res = await api.put(
    `/extras-venta/categorias/${idCategoria}/config`,
    { ids_extras: idsExtras },
    { headers: getAuthHeader() }
  );
  return res.data;
}

export async function getProductoExtrasConfig(idProducto) {
  const res = await api.get(`/extras-venta/productos/${idProducto}/config`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function saveProductoExtrasConfig(idProducto, idsExtras) {
  const res = await api.put(
    `/extras-venta/productos/${idProducto}/config`,
    { ids_extras: idsExtras },
    { headers: getAuthHeader() }
  );
  return res.data;
}
