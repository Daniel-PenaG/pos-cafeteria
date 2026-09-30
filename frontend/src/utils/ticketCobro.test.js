import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { lineasCobroTicket } from "./ticketCobro.js";

describe("ticket 58 mm", () => {
  it("el pago mixto muestra consumo, puntos, efectivo y saldo final", () => {
    const { lineas } = lineasCobroTicket({
      total: 120,
      forma_pago: "MIXTO",
      forma_pago_monetaria: "EFECTIVO",
      puntos_canje: 200,
      equivalencia_puntos: 20,
      importe_monetario: 100,
      puntos_generados: 10,
      saldo_anterior: 300,
      saldo_final: 110,
    });
    assert.deepEqual(lineas, [
      "Total consumo: $120.00",
      "Puntos utilizados: 200 pts",
      "Valor aplicado: $20.00",
      "Efectivo: $100.00",
      "Saldo anterior: 300",
      "Puntos generados: 10",
      "Saldo final: 110",
    ]);
  });

  it("el pago total con puntos no imprime efectivo en cero", () => {
    const { lineas, pagoTotal } = lineasCobroTicket({
      total: 50,
      forma_pago: "PUNTOS",
      puntos_canje: 500,
      equivalencia_puntos: 50,
      importe_monetario: 0,
      puntos_generados: 0,
      saldo_anterior: 500,
      saldo_final: 0,
    });
    assert.equal(pagoTotal, true);
    assert.equal(lineas[1], "PAGADO CON PUNTOS");
    assert.equal(lineas.some((l) => l.startsWith("Efectivo")), false);
    assert.equal(lineas.some((l) => l.startsWith("Recibido")), false);
  });
});