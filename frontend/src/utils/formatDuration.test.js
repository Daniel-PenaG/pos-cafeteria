import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { formatDuration } from "./formatDuration.js";

describe("formatDuration", () => {
  it("65s → 1m 05s", () => {
    assert.equal(formatDuration(65), "1m 05s");
  });

  it("0s", () => {
    assert.equal(formatDuration(0), "0s");
  });

  it("negativo no se muestra como número negativo", () => {
    assert.equal(formatDuration(-3), "—");
  });
});
