import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

describe("CobroExitoModal", () => {
  it("onClose no invoca cobrarPedido ni POST", () => {
    const modal = readFileSync(path.join(root, "components/CobroExitoModal.jsx"), "utf8");
    assert.doesNotMatch(modal, /cobrarPedido/);
    assert.doesNotMatch(modal, /confirmarComanda/);
    assert.match(modal, /useLayoutEffect/);
    assert.match(modal, /modal_hidden/);
    const host = readFileSync(path.join(root, "components/CobroExitoHost.jsx"), "utf8");
    assert.match(host, /closeImmediate/);
    assert.match(host, /flushSync/);
    assert.match(host, /clearResumen/);
    assert.doesNotMatch(host, /cobrarPedido/);
    const ventas = readFileSync(path.join(root, "pages/Ventas.jsx"), "utf8");
    assert.match(ventas, /showCobroExitoResumen/);
    assert.doesNotMatch(ventas, /<CobroExitoModal/);
  });
});
