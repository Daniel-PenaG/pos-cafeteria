import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { createOperationId, isNetworkRetryError } from "./operationId.js";

describe("operationId", () => {
  it("genera UUID distintos por intención", () => {
    const a = createOperationId();
    const b = createOperationId();
    assert.notEqual(a, b);
    assert.match(a, /^[0-9a-f-]{36}$/i);
  });

  it("reintento de red se detecta", () => {
    assert.equal(isNetworkRetryError({ code: "ERR_NETWORK" }), true);
    assert.equal(isNetworkRetryError({ response: { status: 400 } }), false);
  });
});
