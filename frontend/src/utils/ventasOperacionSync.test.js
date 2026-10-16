import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  efectoConfirmarComanda,
  mergeMesaActivaFromPedido,
  sincronizarTrasAgregarLinea,
} from "./ventasOperacionSync.js";

describe("ventasOperacionSync", () => {
  it("agregar línea no llama GET /pedidos/activos", () => {
    const pedido = { id_pedido: 9, total: 70, lineas: [{ id_detalle_pedido: 1 }] };
    const { mesas, llamoGetPedidosActivos } = sincronizarTrasAgregarLinea({}, 4, pedido);
    assert.equal(llamoGetPedidosActivos, false);
    assert.equal(mesas[4].total, 70);
    assert.equal(mesas[4].num_lineas, 1);
  });

  it("mergeMesaActivaFromPedido conserva otras mesas", () => {
    const prev = { 3: { total: 10 }, 4: { total: 20 } };
    const pedido = { id_pedido: 2, total: 55, lineas: [{}, {}] };
    const next = mergeMesaActivaFromPedido(prev, 4, pedido);
    assert.equal(next[3].total, 10);
    assert.equal(next[4].total, 55);
    assert.equal(next[4].num_lineas, 2);
  });

  it("confirmar comanda utiliza respuesta POST sin GET extra", () => {
    const conCuerpo = efectoConfirmarComanda({ id_pedido: 1, lineas: [] });
    assert.equal(conCuerpo.usedPostBody, true);
    assert.equal(conCuerpo.needsFullReload, false);
    const sinCuerpo = efectoConfirmarComanda(null);
    assert.equal(sinCuerpo.needsFullReload, true);
  });
});
