import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  createIntentStore,
  fingerprintCombo,
  fingerprintLinea,
  shouldKeepPendingKey,
  withIntentRetry,
} from "./operationIntent.js";

const mesaA = {
  numeroMesa: 4,
  paraLlevar: false,
};

describe("operationIntent", () => {
  it("timeout de producto A seguido de producto B usa claves distintas", () => {
    const store = createIntentStore();
    const fpA = fingerprintLinea({ ...mesaA, id_producto: 1, precio_unitario: 35 });
    const fpB = fingerprintLinea({ ...mesaA, id_producto: 2, precio_unitario: 45 });
    const keyA = store.beginIntent(fpA);
    assert.equal(store.peek(fpA), keyA);
    const keyB = store.beginIntent(fpB);
    assert.notEqual(keyA, keyB);
    assert.equal(store.peek(fpA), keyA);
    assert.equal(store.peek(fpB), keyB);
  });

  it("timeout de producto seguido de combo no comparte clave", () => {
    const store = createIntentStore();
    const fpLinea = fingerprintLinea({ ...mesaA, id_producto: 1, precio_unitario: 35 });
    const fpCombo = fingerprintCombo({ ...mesaA, id_promocion: 9 });
    const keyLinea = store.beginIntent(fpLinea);
    const keyCombo = store.beginIntent(fpCombo);
    assert.notEqual(keyLinea, keyCombo);
    assert.notEqual(fpLinea, fpCombo);
  });

  it("reutiliza la misma clave solo para el mismo payload pendiente", () => {
    const store = createIntentStore();
    const fp = fingerprintLinea({ ...mesaA, id_producto: 1, precio_unitario: 35 });
    const first = store.beginIntent(fp);
    const retry = store.beginIntent(fp);
    assert.equal(first, retry);
    store.completeIntent(fp);
    const nextTap = store.beginIntent(fp);
    assert.notEqual(first, nextTap);
  });

  it("dos acciones intencionales generan dos claves", () => {
    const store = createIntentStore();
    const fp = fingerprintLinea({ ...mesaA, id_producto: 1, precio_unitario: 35 });
    const first = store.beginIntent(fp);
    store.completeIntent(fp);
    const second = store.beginIntent(fp);
    assert.notEqual(first, second);
    assert.equal(store.size(), 1);
  });

  it("withIntentRetry reintenta una vez con la misma ejecución", async () => {
    const store = createIntentStore();
    const fp = fingerprintLinea({ ...mesaA, id_producto: 3, precio_unitario: 20 });
    const key = store.beginIntent(fp);
    let calls = 0;
    const result = await withIntentRetry(async () => {
      calls += 1;
      assert.equal(store.peek(fp), key);
      if (calls === 1) {
        const err = new Error("timeout of 8000ms exceeded");
        err.code = "ECONNABORTED";
        throw err;
      }
      return { ok: true, operation_id: key };
    });
    assert.equal(calls, 2);
    assert.equal(result.operation_id, key);
    store.completeIntent(fp);
    assert.equal(store.peek(fp), null);
  });

  it("tras timeout conserva la clave; error 4xx la libera", () => {
    const timeoutErr = new Error("network");
    timeoutErr.code = "ERR_NETWORK";
    assert.equal(shouldKeepPendingKey(timeoutErr), true);
    assert.equal(shouldKeepPendingKey({ response: { status: 409 } }), false);
    assert.equal(shouldKeepPendingKey({ response: { status: 400 } }), false);
  });
});
