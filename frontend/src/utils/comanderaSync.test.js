import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  aplicarLineaListo,
  resolveComanderaMutacionError,
  resolveComanderaMutacionExito,
  shouldSkipComanderaFetch,
} from "./comanderaSync.js";

describe("comanderaSync", () => {
  it("marcar listo actualiza estado local sin refresco", () => {
    const lineas = [
      { id_detalle_pedido: 1, cantidad_pendiente: 2 },
      { id_detalle_pedido: 2, cantidad_pendiente: 1 },
    ];
    const ok = resolveComanderaMutacionExito(
      { id_detalle_pedido: 1, cantidad_pendiente: 1 },
      { refrescarEnExito: false }
    );
    assert.equal(ok.action, "local");
    const next = aplicarLineaListo(lineas, ok.detalle);
    assert.equal(next.length, 2);
    assert.equal(next[0].cantidad_pendiente, 1);
  });

  it("retira línea cuando cantidad_pendiente llega a cero", () => {
    const lineas = [{ id_detalle_pedido: 5, cantidad_pendiente: 1 }];
    const next = aplicarLineaListo(lineas, { id_detalle_pedido: 5, cantidad_pendiente: 0 });
    assert.equal(next.length, 0);
  });

  it("409 sí refresca Comandera", () => {
    const fail = resolveComanderaMutacionError(409);
    assert.equal(fail.action, "refresh");
    assert.equal(fail.notifyConflict, true);
  });

  it("polling no se solapa si ya hay carga", () => {
    assert.equal(
      shouldSkipComanderaFetch({ cargando: true, visibilityState: "visible", forzar: false }),
      true
    );
    assert.equal(
      shouldSkipComanderaFetch({ cargando: false, visibilityState: "visible", forzar: false }),
      false
    );
  });

  it("polling se pausa con pestaña oculta", () => {
    assert.equal(
      shouldSkipComanderaFetch({ cargando: false, visibilityState: "hidden", forzar: false }),
      true
    );
    assert.equal(
      shouldSkipComanderaFetch({ cargando: false, visibilityState: "hidden", forzar: true }),
      false
    );
  });
});
