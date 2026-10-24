import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createResourceCache } from "../cache/resourceCache.js";
import { resetPrefetchStateForTests } from "./prefetchRoutes.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

describe("navegación operativa", () => {
  it("Ventas.jsx sin alert/confirm nativos", () => {
    const src = readFileSync(path.join(root, "pages/Ventas.jsx"), "utf8");
    assert.doesNotMatch(src, /\b(window\.)?(alert|confirm)\s*\(/);
  });

  it("Comandera.jsx sin alert/confirm nativos", () => {
    const src = readFileSync(path.join(root, "pages/Comandera.jsx"), "utf8");
    assert.doesNotMatch(src, /\b(window\.)?(alert|confirm)\s*\(/);
  });

  it("latencia simulada mantiene stale visible", async () => {
    const cache = createResourceCache({ ttlMs: 1, sessionKey: () => "lat" });
    await cache.load(async () => ({ ok: true }), { now: 0 });
    await new Promise((r) => setTimeout(r, 5));
    let delayed = false;
    const hit = await cache.load(
      () =>
        new Promise((resolve) => {
          delayed = true;
          setTimeout(() => resolve({ ok: false }), 150);
        }),
      { now: Date.now(), allowStale: true }
    );
    assert.equal(hit.stale, true);
    assert.equal(hit.value.ok, true);
    assert.equal(delayed, true);
  });

  it("prefetch no duplica registro", async () => {
    resetPrefetchStateForTests();
    const { prefetchRoute } = await import("./prefetchRoutes.js");
    prefetchRoute("/ventas");
    prefetchRoute("/ventas");
    resetPrefetchStateForTests();
  });
});
