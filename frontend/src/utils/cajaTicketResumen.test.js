import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { lineasResumenCierre } from "./cajaTicketResumen.js";

describe("resumen de cierre para impresión", () => {
  it("arma líneas sin mutar la sesión", () => {
    const sesion = {
      estado: "CERRADA_CONCILIADA",
      terminal: "CAJA-1",
      ventas_total: 100,
      num_ventas: 2,
      fondo_inicial: 200,
      esperado_efectivo: 250,
      declarado_efectivo: 250,
      diferencia_efectivo: 0,
    };
    const lineas = lineasResumenCierre({ sesion, usuario: { nombre: "Ana" } });
    assert.ok(lineas.some((l) => l.includes("Ana")));
    assert.ok(lineas.some((l) => l.includes("CERRADA_CONCILIADA")));
    assert.ok(lineas.some((l) => l.includes("$250.00")));
    assert.equal(sesion.estado, "CERRADA_CONCILIADA");
  });
});
