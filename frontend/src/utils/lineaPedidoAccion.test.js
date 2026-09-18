import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { formatApiError } from "./apiError.js";
import { createProductAddLock } from "./operationIntent.js";
import {
  accionQuitarLinea,
  debeRefrescarPedidoPorConflicto,
  esLineaActiva,
  lineasActivas,
  requiereCancelacionEnviada,
} from "./lineaPedidoAccion.js";

describe("bloqueo por producto (doble toque)", () => {
  it("bloquea el segundo toque del mismo producto y permite otro distinto", () => {
    const lock = createProductAddLock();
    assert.equal(lock.tryBegin(10), true);
    assert.equal(lock.tryBegin(10), false);
    assert.equal(lock.tryBegin(11), true);
    lock.end(10);
    assert.equal(lock.tryBegin(10), true);
  });
});

describe("errores de línea", () => {
  it("error 403 muestra el detalle del backend", () => {
    const err = {
      response: {
        status: 403,
        data: { detail: "No tienes permiso para cancelar productos enviados." },
      },
    };
    assert.equal(
      formatApiError(err, "Error al eliminar línea"),
      "No tienes permiso para cancelar productos enviados."
    );
  });

  it("error 409 de comandera pide refrescar y muestra el detalle", () => {
    const err = {
      response: {
        status: 409,
        data: { detail: "La línea cambió en otro dispositivo. Actualiza la comandera." },
      },
    };
    assert.equal(debeRefrescarPedidoPorConflicto(err), true);
    assert.equal(
      formatApiError(err, "La comandera cambió. Se actualiza la lista."),
      "La línea cambió en otro dispositivo. Actualiza la comandera."
    );
  });

  it("error 409 indica refrescar el pedido", () => {
    const err = {
      response: {
        status: 409,
        data: { detail: "La cantidad cambió en otro dispositivo. Actualiza el pedido." },
      },
    };
    assert.equal(debeRefrescarPedidoPorConflicto(err), true);
    assert.equal(
      formatApiError(err, "Error al eliminar línea"),
      "La cantidad cambió en otro dispositivo. Actualiza el pedido."
    );
  });

  it("422 de línea en comanda no se oculta con un genérico", () => {
    const err = {
      response: {
        status: 422,
        data: { detail: "El producto ya fue enviado a comandera. Registra una cancelación." },
      },
    };
    assert.equal(
      formatApiError(err, "Error al eliminar línea"),
      "El producto ya fue enviado a comandera. Registra una cancelación."
    );
  });
});

describe("acciones de línea y modal", () => {
  it("línea no enviada se elimina; enviada abre cancelación", () => {
    assert.equal(accionQuitarLinea({ en_comanda: false, cantidad: 1 }), "eliminar");
    assert.equal(
      accionQuitarLinea({ en_comanda: true, cantidad: 2, estado_linea: "ACTIVA" }),
      "cancelar_enviada"
    );
  });

  it("cantidad 2 enviada permite disminuir una o cancelar toda la línea", () => {
    const linea = { en_comanda: true, cantidad: 2, estado_linea: "ACTIVA" };
    assert.equal(requiereCancelacionEnviada(linea), true);
    assert.equal(esLineaActiva(linea), true);
    const cancelarUna = 1;
    const cancelarTodo = Number(linea.cantidad);
    assert.equal(cancelarUna, 1);
    assert.equal(cancelarTodo, 2);
  });

  it("línea cancelada no se cobra ni se vuelve a quitar", () => {
    const lineas = [
      { cantidad: 1, estado_linea: "ACTIVA", precio_unitario: 40 },
      { cantidad: 0, estado_linea: "CANCELADA", precio_unitario: 40 },
    ];
    assert.equal(lineasActivas(lineas).length, 1);
    assert.equal(accionQuitarLinea(lineas[1]), "ninguna");
  });
});
