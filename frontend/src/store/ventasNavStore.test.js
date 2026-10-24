import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  clearAllVentasSessions,
  clearVentasSessionCatalog,
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

  it("clearVentasSessionCatalog quita productos y conserva mesa", () => {
    clearAllVentasSessions();
    writeVentasSession(3, false, {
      numeroMesa: 2,
      productos: [{ id_producto: 1, precio_venta: 99 }],
      categorias: [{ id_categoria: 1 }],
    });
    clearVentasSessionCatalog();
    const snap = readVentasSession(3, false);
    assert.equal(snap.numeroMesa, 2);
    assert.equal(snap.productos, undefined);
    assert.equal(snap.categorias, undefined);
  });
});
