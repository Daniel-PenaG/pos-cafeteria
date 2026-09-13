/** Producto simple: un toque agrega 1 unidad. Extras/promos/combos abren flujo actual. */
export function puedeAgregarRapido(ctx) {
  if (!ctx) return false;
  const paquetes = ctx.paquetes ?? [];
  const promos = ctx.promociones ?? [];
  const extras = ctx.extras ?? [];
  return (
    paquetes.length === 0 &&
    promos.length === 0 &&
    extras.length === 0 &&
    Boolean(ctx.calculo_inicial?.margen_ok)
  );
}

/** Personalizar no debe disparar el agregado rápido. */
export function accionProducto(tipoClick, ctx) {
  if (tipoClick === "personalizar") {
    return "abrir_modal";
  }
  return puedeAgregarRapido(ctx) ? "agregar_rapido" : "abrir_modal_o_confirmar";
}
