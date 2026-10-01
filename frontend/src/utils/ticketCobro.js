import { etiquetaFormaPago } from "./formaPago.js";

function money(valor) {
  return `$${Number(valor || 0).toFixed(2)}`;
}

/** Líneas de 58 mm. La precuenta no usa esta función. */
export function lineasCobroTicket(venta) {
  const lineas = [`Total consumo: ${money(venta?.total)}`];
  const pagoTotal =
    venta?.forma_pago === "PUNTOS" ||
    (Number(venta?.importe_monetario) === 0 && Number(venta?.puntos_canje) > 0);
  if (pagoTotal) {
    lineas.push("PAGADO CON PUNTOS");
    lineas.push(`Puntos utilizados: ${venta.puntos_canje} pts`);
    lineas.push(`Valor aplicado: ${money(venta.equivalencia_puntos)}`);
  } else if (Number(venta?.puntos_canje) > 0) {
    lineas.push(`Puntos utilizados: ${venta.puntos_canje} pts`);
    lineas.push(`Valor aplicado: ${money(venta.equivalencia_puntos)}`);
    const metodo = etiquetaFormaPago(venta?.forma_pago_monetaria || "EFECTIVO");
    lineas.push(`${metodo}: ${money(venta.importe_monetario)}`);
  } else {
    lineas.push(`Pago: ${etiquetaFormaPago(venta?.forma_pago)}`);
  }
  if (venta?.saldo_anterior != null) lineas.push(`Saldo anterior: ${venta.saldo_anterior}`);
  if (Number(venta?.puntos_generados) > 0) {
    lineas.push(`Puntos generados: ${venta.puntos_generados}`);
  }
  if (venta?.saldo_final != null) lineas.push(`Saldo final: ${venta.saldo_final}`);
  return { lineas, pagoTotal };
}
