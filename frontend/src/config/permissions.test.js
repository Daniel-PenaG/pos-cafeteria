import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  ACCION_COBRAR_DESDE_COMANDERA,
  canAccessRoute,
  canCobrarDesdeComandera,
  getEffectiveRoutes,
} from "./permissions.js";

describe("permisos frontend", () => {
  it("rutas efectivas por módulos personalizados", () => {
    const rutas = getEffectiveRoutes("CAJERO", ["/ventas", "/clientes"]);
    assert.deepEqual(rutas, ["/ventas", "/clientes"]);
    assert.equal(canAccessRoute("CAJERO", "/comandera", ["/ventas"]), false);
    assert.equal(canAccessRoute("CAJERO", "/ventas", ["/ventas"]), true);
  });

  it("defaults de rol si no hay módulos", () => {
    assert.equal(canAccessRoute("COCINA", "/comandera"), true);
    assert.equal(canAccessRoute("COCINA", "/ventas"), false);
  });

  it("cobro desde comandera según acción", () => {
    assert.equal(canCobrarDesdeComandera({ rol: "COCINA", permisos_acciones: [] }), false);
    assert.equal(
      canCobrarDesdeComandera({
        rol: "COCINA",
        permisos_acciones: [ACCION_COBRAR_DESDE_COMANDERA],
      }),
      true
    );
    assert.equal(canCobrarDesdeComandera({ rol: "ADMIN" }), true);
  });
});
