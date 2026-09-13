import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { accionProducto, puedeAgregarRapido } from "./agregadoRapido.js";

const simple = {
  extras: [],
  promociones: [],
  paquetes: [],
  calculo_inicial: { margen_ok: true, precio_unitario: 50 },
};

describe("agregado rápido y Personalizar", () => {
  it("producto simple se agrega rápido", () => {
    assert.equal(puedeAgregarRapido(simple), true);
    assert.equal(accionProducto("click", simple), "agregar_rapido");
  });

  it("Personalizar nunca agrega, solo abre modal", () => {
    assert.equal(accionProducto("personalizar", simple), "abrir_modal");
    assert.equal(accionProducto("personalizar", { ...simple, extras: [{ id: 1 }] }), "abrir_modal");
  });

  it("con extras o promo no es agregado rápido", () => {
    assert.equal(puedeAgregarRapido({ ...simple, extras: [{ id_extra: 1 }] }), false);
    assert.equal(puedeAgregarRapido({ ...simple, promociones: [{ id_promocion: 1 }] }), false);
    assert.equal(puedeAgregarRapido({ ...simple, paquetes: [{ id_promocion: 2 }] }), false);
  });
});
