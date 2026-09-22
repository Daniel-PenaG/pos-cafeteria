import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  ACCION_ABRIR_CAJA,
  ACCION_COBRAR_DESDE_COMANDERA,
  ACCION_CANCELAR_PRODUCTO_EN_COMANDA,
  ACCION_REVISAR_CIERRE_CAJA,
  canAccessRoute,
  canCancelarProductoEnComanda,
  canCobrarDesdeComandera,
  getEffectiveRoutes,
  hasAction,
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
    assert.deepEqual(getEffectiveRoutes("CAJERO", null), [
      "/dashboard",
      "/ventas",
      "/mesas-activas",
      "/ventas-para-llevar",
      "/comandera",
      "/clientes",
      "/cierre-caja",
    ]);
  });

  it("lista vacía no usa defaults del rol", () => {
    assert.deepEqual(getEffectiveRoutes("CAJERO", []), []);
    assert.equal(canAccessRoute("CAJERO", "/ventas", []), false);
    assert.equal(canAccessRoute("COCINA", "/comandera", []), false);
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

  it("cancelar producto en comandera según acción", () => {
    assert.equal(
      canCancelarProductoEnComanda({ rol: "CAJERO", permisos_acciones: [] }),
      false
    );
    assert.equal(
      canCancelarProductoEnComanda({
        rol: "CAJERO",
        permisos_acciones: [ACCION_CANCELAR_PRODUCTO_EN_COMANDA],
      }),
      true
    );
    assert.equal(
      canCancelarProductoEnComanda({ rol: "COCINA", permisos_acciones: [] }),
      false
    );
    assert.equal(canCancelarProductoEnComanda({ rol: "ADMIN" }), true);
  });

  it("caja: ADMIN todas, COCINA ninguna, CAJERO las concedidas", () => {
    assert.equal(hasAction("ADMIN", ACCION_ABRIR_CAJA), true);
    assert.equal(hasAction("COCINA", ACCION_ABRIR_CAJA, []), false);
    assert.equal(hasAction("CAJERO", ACCION_ABRIR_CAJA, [ACCION_ABRIR_CAJA]), true);
    assert.equal(hasAction("CAJERO", ACCION_REVISAR_CIERRE_CAJA, [ACCION_ABRIR_CAJA]), false);
  });
});
