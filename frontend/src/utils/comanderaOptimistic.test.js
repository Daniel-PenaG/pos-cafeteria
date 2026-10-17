import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  applyOptimisticListoPlan,
  buildOptimisticListoPlan,
  isStaleListoOp,
  reconcileListoServerLine,
  resolveComanderaMutacionError,
  rollbackOptimisticLinea,
} from "./comanderaSync.js";

describe("Comandera optimista (listo)", () => {
  const linea = {
    id_detalle_pedido: 9,
    cantidad: 2,
    cantidad_pendiente: 2,
    cantidad_lista: 0,
    nombre_producto: "Test",
  };

  it("feedback visual inmediato reduce pendiente", () => {
    const plan = buildOptimisticListoPlan(linea, 1);
    assert.equal(plan.kind, "patch");
    const next = applyOptimisticListoPlan([linea], plan);
    assert.equal(next[0].cantidad_pendiente, 1);
    assert.equal(next[0].cantidad_lista, 1);
  });

  it("doble plan sobre misma línea: segundo patch coherente", () => {
    const plan1 = buildOptimisticListoPlan(linea, 1);
    const mid = applyOptimisticListoPlan([linea], plan1);
    const plan2 = buildOptimisticListoPlan(mid[0], 1);
    assert.equal(plan2.kind, "remove");
  });

  it("rollback por error restaura snapshot", () => {
    const plan = buildOptimisticListoPlan(linea, 1);
    const next = applyOptimisticListoPlan([linea], plan);
    const restored = rollbackOptimisticLinea(next, plan.rollback);
    assert.deepEqual(restored[0], linea);
  });

  it("409 refresca vía resolveComanderaMutacionError", () => {
    assert.equal(resolveComanderaMutacionError(409).action, "refresh");
  });

  it("respuesta vieja ignorada con isStaleListoOp", () => {
    assert.equal(isStaleListoOp(1, 2), true);
    assert.equal(isStaleListoOp(2, 2), false);
  });

  it("reconcile no pisa cuando stale", () => {
    const lineas = [{ id_detalle_pedido: 9, cantidad_pendiente: 0 }];
    const out = reconcileListoServerLine(
      lineas,
      { id_detalle_pedido: 9, cantidad_pendiente: 1 },
      { stale: true }
    );
    assert.equal(out.length, 1);
    assert.equal(out[0].cantidad_pendiente, 0);
  });

  it("línea eliminada optimista no reaparece si allowReinsert false", () => {
    const plan = buildOptimisticListoPlan(linea, 2);
    const empty = applyOptimisticListoPlan([linea], plan);
    assert.equal(empty.length, 0);
    const noInsert = rollbackOptimisticLinea(empty, plan.rollback, { allowReinsert: false });
    assert.equal(noInsert.length, 0);
  });
});
