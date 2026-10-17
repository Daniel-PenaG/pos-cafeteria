import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  clearAllVentasSessions,
  readVentasSession,
  writeVentasSession,
} from "./ventasNavStore.js";

describe("ventasNavStore", () => {
  it("conserva mesa y pedido por usuario", () => {
    clearAllVentasSessions();
    writeVentasSession(7, false, { numeroMesa: 3, pedido: { id_pedido: 9 } });
    const snap = readVentasSession(7, false);
    assert.equal(snap.numeroMesa, 3);
    assert.equal(snap.pedido.id_pedido, 9);
  });

  it("no mezcla usuarios", () => {
    clearAllVentasSessions();
    writeVentasSession(1, false, { numeroMesa: 1 });
    writeVentasSession(2, false, { numeroMesa: 5 });
    assert.equal(readVentasSession(1, false).numeroMesa, 1);
    assert.equal(readVentasSession(2, false).numeroMesa, 5);
  });
});
