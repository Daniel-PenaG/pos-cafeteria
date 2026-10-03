import api from "../api/axios";

export const getEstadoTesoreria = () => api.get("/tesoreria/estado").then((r) => r.data);
export const getCuentasTesoreria = () => api.get("/tesoreria/cuentas").then((r) => r.data);
export const getResumenTesoreria = () => api.get("/tesoreria/resumen").then((r) => r.data);
export const getMovimientosTesoreria = (params) =>
  api.get("/tesoreria/movimientos", { params }).then((r) => r.data);
export const getConciliaciones = () => api.get("/tesoreria/conciliaciones").then((r) => r.data);

export const activarTesoreria = (payload) => api.post("/tesoreria/activar", payload).then((r) => r.data);
export const crearTraspaso = (payload) => api.post("/tesoreria/traspasos", payload).then((r) => r.data);
export const crearAportacion = (payload) => api.post("/tesoreria/aportaciones", payload).then((r) => r.data);
export const crearRetiro = (payload) => api.post("/tesoreria/retiros", payload).then((r) => r.data);
export const crearComision = (payload) => api.post("/tesoreria/comisiones", payload).then((r) => r.data);
export const crearAjuste = (payload) => api.post("/tesoreria/ajustes", payload).then((r) => r.data);
export const revertirOperacion = (id, payload) =>
  api.post(`/tesoreria/operaciones/${id}/revertir`, payload).then((r) => r.data);
export const crearConciliacion = (payload) => api.post("/tesoreria/conciliaciones", payload).then((r) => r.data);
export const revisarConciliacion = (id, payload) =>
  api.post(`/tesoreria/conciliaciones/${id}/revisar`, payload).then((r) => r.data);
