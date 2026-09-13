import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { PRODUCTO_CONTEXTO_TTL_MS, createContextoCache } from "./productoContextoCache.js";

describe("caché contexto producto", () => {
  it("TTL es 30 segundos", () => {
    assert.equal(PRODUCTO_CONTEXTO_TTL_MS, 30_000);
  });

  it("devuelve hit antes de expirar", () => {
    const cache = createContextoCache();
    const now = 1_000_000;
    cache.set(7, { ok: true }, now);
    assert.deepEqual(cache.get(7, now + 10_000), { ok: true });
  });

  it("expira y no deja dato viejo (promos vigentes)", () => {
    const cache = createContextoCache();
    const now = 1_000_000;
    cache.set(7, { promo: "antes" }, now);
    assert.equal(cache.get(7, now + PRODUCTO_CONTEXTO_TTL_MS + 1), null);
  });
});
