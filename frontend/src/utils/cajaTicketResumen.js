export function lineasResumenCierre({ sesion, usuario, cafeteria = "Coffe Song" }) {
  const money = (n) => `$${Number(n || 0).toFixed(2)}`;
  return [
    `Cafeteria: ${cafeteria}`,
    `Cajero: ${usuario?.nombre || sesion?.usuario_nombre || "—"}`,
    `Terminal: ${sesion?.terminal || "—"}`,
    `Estado: ${sesion?.estado || "—"}`,
    `Ventas total: ${money(sesion?.ventas_total)}`,
    `Tickets: ${sesion?.num_ventas ?? 0}`,
    `Fondo inicial: ${money(sesion?.fondo_inicial)}`,
    `Entradas: ${money(sesion?.entradas)}`,
    `Retiros: ${money(sesion?.retiros)}`,
    `Gastos caja: ${money(sesion?.gastos_caja)}`,
    `Ef. esperado: ${money(sesion?.esperado_efectivo ?? sesion?.efectivo_esperado)}`,
    `Ef. contado: ${money(sesion?.declarado_efectivo)}`,
    `Dif. efectivo: ${money(sesion?.diferencia_efectivo)}`,
    `Trans. esp.: ${money(sesion?.esperado_transferencia)}`,
    `Term. esp.: ${money(sesion?.esperado_tarjeta)}`,
  ];
}
