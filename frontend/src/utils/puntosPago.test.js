import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  botonCobroBloqueado,
  cambioEfectivo,
  clientePrecargado,
  evaluarCanje,
  evaluarCanjeCliente,
  exigeMetodoMonetario,
  maxPuntosCanje,
  ocultaMetodoMonetario,
  payloadCobro,
  puntosGeneradosEstimados,
  resolverErrorCobro,
  saldoFinalEstimado,
} from "./puntosPago.js";

describe("canje de puntos", () => {
  it("un ticket menor a $5 no habilita canje", () => {
    assert.equal(maxPuntosCanje(4.99, 500), 0);
    const r = evaluarCanje(4, 500, "50");
    assert.equal(r.bloquea, true);
    assert.equal(r.puntos, 0);
  });

  it("limita al saldo y al total en múltiplos de 10", () => {
    assert.equal(maxPuntosCanje(120, 255), 250);
    assert.equal(maxPuntosCanje(50, 1000), 500);
    assert.equal(maxPuntosCanje(120, 40), 0);
  });

  it("calcula el remanente monetario", () => {
    const r = evaluarCanje(120, 1000, "200");
    assert.equal(r.puntos, 200);
    assert.equal(r.equivalencia, 20);
    assert.equal(r.importe, 100);
    assert.equal(r.bloquea, false);
  });

  it("rechaza menos de 50 y cantidades que no son múltiplo de 10", () => {
    assert.equal(evaluarCanje(120, 1000, "40").bloquea, true);
    assert.equal(evaluarCanje(120, 1000, "49").bloquea, true);
    assert.equal(evaluarCanje(120, 1000, "55").bloquea, true);
    assert.equal(evaluarCanje(50, 1000, "60").equivalencia, 6);
    assert.equal(evaluarCanje(50, 1000, "50").equivalencia, 5);
  });

  it("el cambio y el remanente de un centavo no usan error binario", () => {
    const r = evaluarCanje(50.5, 1000, "500");
    assert.equal(r.importe, 0.5);
    assert.equal(cambioEfectivo(0.3, 0.1), 0.2);
    assert.equal(evaluarCanje(50.01, 500, "500").importe, 0.01);
  });

  it("teléfono, QR y cliente nuevo envían el id del cliente seleccionado", () => {
    for (const origen of ["telefono", "qr", "nuevo"]) {
      const body = payloadCobro({
        idUsuario: 7,
        formaPago: "EFECTIVO",
        cliente: { id_cliente: 4, origen },
        conCliente: true,
        puntos: 200,
        operationId: `op-${origen}`,
      });
      assert.equal(body.id_cliente, 4);
      assert.equal(body.puntos_canje, 200);
      assert.equal(body.id_usuario, 7);
    }
    const sin = payloadCobro({
      idUsuario: 7,
      formaPago: "EFECTIVO",
      cliente: { id_cliente: 4 },
      conCliente: false,
      puntos: 200,
      operationId: "op-sin",
    });
    assert.equal(sin.id_cliente, null);
    assert.equal(sin.puntos_canje, 0);
  });

  it("50 puntos habilitan $5 y 200 puntos equivalen a $20", () => {
    const cincuenta = evaluarCanje(50, 100, "50");
    assert.equal(cincuenta.bloquea, false);
    assert.equal(cincuenta.equivalencia, 5);
    const doscientos = evaluarCanje(120, 1000, "200");
    assert.equal(doscientos.equivalencia, 20);
    assert.equal(doscientos.importe, 100);
  });

  it("el pago completo oculta el método y el mixto lo exige", () => {
    const completo = evaluarCanje(50, 500, "500");
    assert.equal(ocultaMetodoMonetario(completo), true);
    assert.equal(exigeMetodoMonetario(completo), false);
    const mixto = evaluarCanje(120, 1000, "200");
    assert.equal(ocultaMetodoMonetario(mixto), false);
    assert.equal(exigeMetodoMonetario(mixto), true);
  });

  it("el cambio de efectivo usa el remanente, no el total", () => {
    const mixto = evaluarCanje(120, 1000, "200");
    assert.equal(cambioEfectivo(150, mixto.importe), 50);
    assert.equal(cambioEfectivo(150, 120), 30);
  });

  it("la parte pagada con puntos no genera puntos", () => {
    const mixto = evaluarCanje(120, 1000, "200");
    assert.equal(puntosGeneradosEstimados(mixto.importe), 10);
    assert.equal(puntosGeneradosEstimados(0), 0);
    assert.equal(puntosGeneradosEstimados(evaluarCanje(50, 500, "500").importe), 0);
    assert.equal(saldoFinalEstimado(300, 200, puntosGeneradosEstimados(mixto.importe)), 110);
  });

  it("el doble toque deja el botón bloqueado", () => {
    assert.equal(botonCobroBloqueado({ loading: true, bloquea: false }), true);
    assert.equal(botonCobroBloqueado({ loading: false, bloquea: true }), true);
    assert.equal(botonCobroBloqueado({ loading: false, bloquea: false }), false);
  });

  it("un 409 refresca el saldo y conserva el pedido", () => {
    const efecto = resolverErrorCobro(409, {
      detail: "El saldo de puntos cambió; revisa nuevamente.",
      codigo: "SALDO_PUNTOS_CAMBIO",
      saldo_actual: 40,
    });
    assert.equal(efecto.conservaPedido, true);
    assert.equal(efecto.cierraModal, false);
    assert.equal(efecto.refrescaSaldo, true);
    assert.equal(efecto.reintentar, false);
    assert.equal(efecto.saldoActual, 40);
    assert.equal(resolverErrorCobro(422).refrescaSaldo, false);
    assert.equal(resolverErrorCobro(422).reintentar, false);
  });

  it("el cliente del pedido se precarga y quitarlo es explícito", () => {
    const pedido = {
      id_cliente: 4,
      cliente_nombre: "Ana",
      cliente_puntos_saldo: 300,
      cliente_activo: true,
    };
    const cliente = clientePrecargado(pedido);
    assert.equal(cliente.id_cliente, 4);
    assert.equal(cliente.nombre, "Ana");
    assert.equal(cliente.puntos_saldo, 300);
    assert.equal(clientePrecargado({}), null);
    const quitado = payloadCobro({
      idUsuario: 1,
      formaPago: "EFECTIVO",
      cliente,
      conCliente: false,
      puntos: 0,
      operationId: "op-quitar",
      desasociarCliente: true,
    });
    assert.equal(quitado.id_cliente, null);
    assert.equal(quitado.puntos_canje, 0);
    assert.equal(quitado.desasociar_cliente, true);
    const cerrado = clientePrecargado(pedido);
    assert.equal(cerrado.id_cliente, cliente.id_cliente);
  });

  it("un cliente inactivo no puede canjear", () => {
    const r = evaluarCanjeCliente(120, { activo: false, puntos_saldo: 500 }, "200");
    assert.equal(r.bloquea, true);
    assert.equal(r.habilitado, false);
    assert.match(r.error, /inactivo/);
  });
});
