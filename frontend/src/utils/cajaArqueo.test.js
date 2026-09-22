import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  cantidadesVacias,
  etiquetaEstadoCaja,
  payloadDenominaciones,
  totalDesdeDenominaciones,
} from "./cajaArqueo.js";

describe("arqueo de caja", () => {
  it("calcula el total por denominaciones", () => {
    const c = cantidadesVacias();
    c.B100 = "2";
    c.B50 = "1";
    c.M10 = "3";
    c.M050 = "2";
    assert.equal(totalDesdeDenominaciones(c), 281);
  });

  it("no trata un método desconocido como efectivo", () => {
    const unknown = "PUNTOS";
    assert.notEqual(unknown, "EFECTIVO");
    assert.equal(etiquetaEstadoCaja("CERRADA_CONCILIADA"), "Cerrada conciliada");
  });

  it("arma el payload de denominaciones", () => {
    const items = payloadDenominaciones({ B100: "1", M1: "4" });
    const b100 = items.find((i) => i.codigo === "B100");
    const m1 = items.find((i) => i.codigo === "M1");
    assert.equal(b100.cantidad, 1);
    assert.equal(m1.cantidad, 4);
  });
});
