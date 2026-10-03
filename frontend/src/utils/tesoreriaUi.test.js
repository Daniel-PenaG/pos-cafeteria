import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  botonBloqueado,
  columnasTesoreria,
  diferenciaConciliacion,
  efectoErrorTesoreria,
  esGastoOperativo,
  formatoMxn,
  movimientoMonetario,
  saldoVisible,
  validarTraspaso,
} from "./tesoreriaUi.js";

describe("tesorería visual", () => {
  it("formatea MXN con dos decimales", () => {
    assert.match(formatoMxn(112), /112\.00/);
    assert.match(formatoMxn("70.5"), /70\.50/);
  });

  it("el saldo visible es entradas menos salidas", () => {
    assert.equal(saldoVisible(200, 88), 112);
  });

  it("rechaza origen igual a destino y el importe mayor al disponible", () => {
    assert.match(validarTraspaso({ origen: "BANCO", destino: "BANCO", importe: 10, disponible: 50 }), /misma/);
    assert.match(
      validarTraspaso({ origen: "EFECTIVO_CASA", destino: "BANCO", importe: 80, disponible: 50 }),
      /supera/
    );
    assert.equal(
      validarTraspaso({ origen: "EFECTIVO_CASA", destino: "BANCO", importe: 40, disponible: 50 }),
      ""
    );
  });

  it("puntos no mueven dinero y el mixto usa el remanente", () => {
    assert.equal(movimientoMonetario("PUNTOS", 42, 42), 0);
    assert.equal(movimientoMonetario("PUNTOS+EFECTIVO", 10, 42), 32);
    assert.equal(movimientoMonetario("EFECTIVO", 42, 42), 42);
  });

  it("el retiro del propietario no es gasto operativo", () => {
    assert.equal(esGastoOperativo("GASTO_OPERATIVO"), true);
    assert.equal(esGastoOperativo("RETIRO_PROPIETARIO"), false);
  });

  it("409 no duplica y 403 no cierra sesión", () => {
    assert.deepEqual(efectoErrorTesoreria(409), { duplica: false, cierraSesion: false });
    assert.deepEqual(efectoErrorTesoreria(403), { duplica: false, cierraSesion: false });
    assert.equal(efectoErrorTesoreria(401).cierraSesion, true);
  });

  it("la conciliación calcula la diferencia sin cambiar el saldo", () => {
    assert.equal(diferenciaConciliacion(100, 90), -10);
    assert.equal(diferenciaConciliacion(100, 100), 0);
  });

  it("bloquea el botón mientras se envía y usa una columna en el celular", () => {
    assert.equal(botonBloqueado(false), false);
    assert.equal(botonBloqueado(true), true);
    assert.equal(columnasTesoreria(390), 1);
    assert.equal(columnasTesoreria(480), 1);
    assert.equal(columnasTesoreria(768), 3);
    assert.equal(columnasTesoreria(1366), 3);
  });
});
