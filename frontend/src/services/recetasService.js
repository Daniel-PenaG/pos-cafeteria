import api from "../api/axios";
import { useAuthStore } from "../store/authStore";

function getAuthHeader() {
  const token = useAuthStore.getState().token;
  return { Authorization: `Bearer ${token}` };
}

export async function getRecetas() {
  const res = await api.get("/recetas", { headers: getAuthHeader() });
  return res.data;
}

// Devuelve una receta con sus insumos
export async function getReceta(id) {
  const res = await api.get(`/recetas/${id}`, { headers: getAuthHeader() });
  return res.data;
}

export async function createReceta(data) {
  console.log("📤 Enviando receta:", JSON.stringify(data, null, 2));
  try {
    const res = await api.post("/recetas", data, { headers: getAuthHeader() });
    return res.data;
  } catch (error) {
    console.error("❌ Error en createReceta:", error.response?.data || error.message);
    throw error;
  }
}

export async function updateReceta(id, data) {
  console.log(`📤 Actualizando receta ${id}:`, JSON.stringify(data, null, 2));
  try {
    const res = await api.put(`/recetas/${id}`, data, { headers: getAuthHeader() });
    return res.data;
  } catch (error) {
    console.error("❌ Error en updateReceta:", error.response?.data || error.message);
    throw error;
  }
}

export async function deleteReceta(id) {
  const res = await api.delete(`/recetas/${id}`, { headers: getAuthHeader() });
  return res.data;
}
