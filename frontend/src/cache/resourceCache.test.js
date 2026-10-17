import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { createResourceCache } from "./resourceCache.js";

describe("resourceCache", () => {
  it("deduplica requests concurrentes", async () => {
    let calls = 0;
    const cache = createResourceCache({ ttlMs: 1000, sessionKey: () => "a" });
    const fetcher = async () => {
      calls += 1;
      await new Promise((r) => setTimeout(r, 20));
      return { n: calls };
    };
    const [a, b] = await Promise.all([cache.load(fetcher), cache.load(fetcher)]);
    assert.equal(calls, 1);
    assert.equal(a.value.n, 1);
    assert.equal(b.value.n, 1);
  });

  it("stale-while-revalidate devuelve dato previo", async () => {
    let v = 1;
    const cache = createResourceCache({ ttlMs: 5, sessionKey: () => "b" });
    await cache.load(async () => v);
    v = 2;
    await new Promise((r) => setTimeout(r, 10));
    const hit = await cache.load(async () => v);
    assert.equal(hit.stale, true);
    assert.equal(hit.value, 1);
    await new Promise((r) => setTimeout(r, 40));
    const fresh = await cache.load(async () => v, { force: true });
    assert.equal(fresh.value, 2);
  });

  it("reset por cambio de sesión", async () => {
    let sk = "u1";
    const cache = createResourceCache({ ttlMs: 5000, sessionKey: () => sk });
    await cache.load(async () => "A");
    sk = "u2";
    const miss = cache.peek();
    assert.equal(miss, null);
  });

  it("usuarios distintos no comparten promesa", async () => {
    let sk = "uA";
    let calls = 0;
    const cache = createResourceCache({ ttlMs: 5000, sessionKey: () => sk });
    const slow = (label) =>
      new Promise((resolve) => {
        calls += 1;
        setTimeout(() => resolve(label), 40);
      });
    const p1 = cache.load(() => slow("A"));
    sk = "uB";
    const p2 = cache.load(() => slow("B"));
    const [a, b] = await Promise.all([p1, p2]);
    assert.equal(calls, 2);
    assert.equal(a.value, "A");
    assert.equal(b.value, "B");
  });

  it("reset impide que inflight anterior repueble caché", async () => {
    const cache = createResourceCache({ ttlMs: 5000, sessionKey: () => "u1" });
    let resolveSlow;
    const slow = new Promise((resolve) => {
      resolveSlow = resolve;
    });
    const pending = cache.load(() => slow);
    cache.reset();
    resolveSlow("stale");
    await pending.catch(() => {});
    assert.equal(cache.peek(), null);
  });

  it("fallo elimina inflight y permite reintentar", async () => {
    let calls = 0;
    const cache = createResourceCache({ ttlMs: 5000, sessionKey: () => "r" });
    const fail = async () => {
      calls += 1;
      if (calls === 1) throw new Error("fail");
      return "ok";
    };
    await assert.rejects(() => cache.load(fail));
    const hit = await cache.load(fail);
    assert.equal(hit.value, "ok");
    assert.equal(calls, 2);
  });
});
