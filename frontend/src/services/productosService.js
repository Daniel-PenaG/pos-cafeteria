import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

// CATEGORÍAS
export async function getCategorias() {
  const res = await api.get("/catalogo/categorias", { headers: getAuthHeader() });
  return res.data;
}

export async function getCategoria(id) {
  const res = await api.get(`/catalogo/categorias/${id}`, { headers: getAuthHeader() });
  return res.data;
}

export async function createCategoria(data) {
  const res = await api.post("/catalogo/categorias", data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function updateCategoria(id, data) {
  const res = await api.put(`/catalogo/categorias/${id}`, data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function deleteCategoria(id) {
  const res = await api.delete(`/catalogo/categorias/${id}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

// PRODUCTOS
export async function getProductos() {
  const res = await api.get("/catalogo/productos", { headers: getAuthHeader() });
  return res.data;
}

export async function getProducto(id) {
  const res = await api.get(`/catalogo/productos/${id}`, { headers: getAuthHeader() });
  return res.data;
}

export async function createProducto(data) {
  const res = await api.post("/catalogo/productos", data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function updateProducto(id, data) {
  const res = await api.put(`/catalogo/productos/${id}`, data, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function deleteProducto(id) {
  const res = await api.delete(`/catalogo/productos/${id}`, {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function getProductosParaLlevar() {
  const res = await api.get("/catalogo/productos/para-llevar", {
    headers: getAuthHeader(),
  });
  return res.data;
}

export async function saveParaLlevarConfig(idsProductos) {
  const res = await api.put(
    "/catalogo/productos/para-llevar/config",
    { ids_productos: idsProductos },
    { headers: getAuthHeader() }
  );
  return res.data;
}
