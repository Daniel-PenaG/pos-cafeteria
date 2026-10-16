import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  appendInventarioAMensajeCobro,
  buildResumenInventarioCobro,
  mensajeCobroInventarioAcotado,
} from "./cobroAdvertencias.js";

describe("cobroAdvertencias", () => {
  it("advertencias resumidas no generan alert gigante", () => {
    const muchos = Array.from({ length: 40 }, (_, i) => ({
      nombre: `Insumo ${i}`,
      disponible: 0,
      requerido: 10,
    }));
    const { esResumido, total } = buildResumenInventarioCobro(muchos);
    assert.equal(total, 40);
    assert.equal(esResumido, true);
    const msg = appendInventarioAMensajeCobro("Cobro ok", muchos);
    assert.equal(mensajeCobroInventarioAcotado(msg), true);
    assert.match(msg, /… y 37 más/);
    assert.doesNotMatch(msg, /Insumo 39/);
  });

  it("sin faltantes no altera mensaje", () => {
    assert.equal(appendInventarioAMensajeCobro("Solo total", []), "Solo total");
  });
});
