import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  OPCION_PRECIO_NORMAL,
  importeLinea,
  promoIncompletaBloqueaCobro,
  sumaImportes,
  textoPrecioLinea,
} from "./promoCantidad.js";

describe("precio de promoción por cantidad", () => {
  it("cantidad 1 muestra precio normal", () => {
    const texto = textoPrecioLinea({
      aplicaciones: 0,
      unidades_normales: 1,
      total_linea: 42,
    });
    assert.match(texto, /Precio normal/);
    assert.match(texto, /\$42\.00/);
  });

  it("cantidad 2 muestra la promoción", () => {
    const texto = textoPrecioLinea({
      aplicaciones: 1,
      unidades_normales: 0,
      total_linea: 70,
    });
    assert.match(texto, /1 promoción/);
    assert.match(texto, /\$70\.00/);
  });

  it("cantidad 3 muestra promoción y sobrante normal", () => {
    const texto = textoPrecioLinea({
      aplicaciones: 1,
      unidades_normales: 1,
      total_linea: 112,
    });
    assert.match(texto, /1 promoción \+ 1 a precio normal/);
    assert.match(texto, /\$112\.00/);
  });

  it("al reducir la cantidad desaparece la promoción", () => {
    const dos = textoPrecioLinea({ aplicaciones: 1, unidades_normales: 0, total_linea: 70 });
    const uno = textoPrecioLinea({ aplicaciones: 0, unidades_normales: 1, total_linea: 42 });
    assert.match(dos, /promoción/);
    assert.match(uno, /Precio normal/);
    assert.doesNotMatch(uno, /promoción/);
  });

  it("el cajero puede elegir precio normal", () => {
    assert.equal(OPCION_PRECIO_NORMAL, "Precio normal");
  });

  it("una cantidad incompleta no bloquea el cobro", () => {
    assert.equal(promoIncompletaBloqueaCobro(), false);
  });

  it("el subtotal manda cuando el promedio no cierra", () => {
    const item = { cantidad: 3, precio_unitario: 42, subtotal: 112 };
    assert.equal(importeLinea(item), 112);
    assert.equal(sumaImportes([item, { subtotal: 70 }]), 182);
    assert.notEqual(item.cantidad * item.precio_unitario, item.subtotal);
  });
});
