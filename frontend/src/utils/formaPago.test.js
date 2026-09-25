import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { bucketFormaPago, esEfectivo, etiquetaFormaPago } from "./formaPago.js";

describe("forma de pago", () => {
  it("nulo o vacío se trata como efectivo histórico", () => {
    assert.equal(bucketFormaPago(null), "EFECTIVO");
    assert.equal(bucketFormaPago(""), "EFECTIVO");
  });

  it("PUNTOS y desconocidos no incrementan efectivo", () => {
    assert.equal(bucketFormaPago("PUNTOS"), "DESCONOCIDO");
    assert.equal(bucketFormaPago("BITCOIN"), "DESCONOCIDO");
    assert.equal(esEfectivo("PUNTOS"), false);
    assert.equal(esEfectivo("DESCONOCIDO"), false);
    assert.equal(etiquetaFormaPago("DESCONOCIDO"), "Desconocido");
  });
});
