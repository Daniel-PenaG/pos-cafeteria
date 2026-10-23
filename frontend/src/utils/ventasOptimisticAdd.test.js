import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { aplicarAgregadoOptimista, aplicarLineaPersonalizadaOptimista } from "./ventasOptimisticAdd.js";

const calculo = {
  margen_ok: true,
  precio_unitario: 42,
  precio_original_unitario: 42,
  total_linea: 42,
};

describe("ventasOptimisticAdd", () => {
  it("añade línea nueva y total", () => {
    const pedido = { id_pedido: 1, lineas: [], total: 0 };
    const producto = { id_producto: 5, nombre: "Latte" };
    const next = aplicarAgregadoOptimista(pedido, producto, calculo);
    assert.equal(next.lineas.length, 1);
    assert.equal(next.lineas[0].nombre_producto, "Latte");
    assert.equal(next.total, 42);
  });

  it("modal con extras agrega línea con detalle", () => {
    const pedido = { id_pedido: 1, lineas: [], total: 0 };
    const producto = { id_producto: 3, nombre: "Latte" };
    const next = aplicarLineaPersonalizadaOptimista(pedido, producto, calculo, {
      cantidad: 1,
      extras: [{ id_extra: 1, nombre: "Vainilla", precio: 5 }],
    });
    assert.equal(next.lineas.length, 1);
    assert.equal(next.lineas[0].extras.length, 1);
    assert.equal(next.total, 42);
  });

  it("incrementa línea pendiente del mismo producto", () => {
    const pedido = {
      id_pedido: 1,
      total: 42,
      lineas: [
        {
          id_detalle_pedido: 10,
          id_producto: 5,
          nombre_producto: "Latte",
          cantidad: 1,
          cantidad_lista: 0,
          cantidad_pendiente: 1,
          precio_unitario: 42,
          subtotal: 42,
          extras: [],
          en_comanda: false,
          estado_linea: "ACTIVA",
        },
      ],
    };
    const producto = { id_producto: 5, nombre: "Latte" };
    const next = aplicarAgregadoOptimista(pedido, producto, calculo);
    assert.equal(next.lineas.length, 1);
    assert.equal(next.lineas[0].cantidad, 2);
    assert.equal(next.total, 84);
  });
});
