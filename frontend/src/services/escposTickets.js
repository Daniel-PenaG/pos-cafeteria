import ThermalPrinterEncoder from "thermal-printer-encoder";
import { etiquetaFormaPago } from "../utils/formaPago";

const WIDTH = 32; // 58 mm ~ 32 chars
const BRAND_NAME = "Coffe Song";
const BRAND_TAGLINE = "Caliente, fresco y al dia";

function encoder() {
  return new ThermalPrinterEncoder({
    language: "esc-pos",
    width: WIDTH,
    wordWrap: true,
  });
}

/** Encabezado de marca para tickets (58 mm). */
export function appendCoffeeSongHeader(enc) {
  enc
    .align("center")
    .line("================================")
    .newline()
    .bold(true)
    .line(BRAND_NAME.toUpperCase())
    .bold(false)
    .newline()
    .line(`· ${BRAND_TAGLINE} ·`)
    .line("================================")
    .newline();
}

/** Ticket de prueba desde configuración de impresora. */
export function buildTestTicket() {
  const enc = encoder();
  appendCoffeeSongHeader(enc);
  enc
    .align("center")
    .line("Prueba de impresion")
    .line(new Date().toLocaleString("es-MX"))
    .newline()
    .line("58 mm · Bluetooth OK")
    .newline()
    .line("--------------------------------")
    .line("Gracias por elegirnos")
    .newline()
    .cut();
  return enc.encode();
}

function lineExtras(extras) {
  if (!extras?.length) return [];
  return extras.map((e) => {
    const precio =
      Number(e.precio) > 0 ? ` (+$${Number(e.precio).toFixed(2)})` : "";
    return `  + ${e.nombre}${precio}`;
  });
}

function mesaOrigenLabel(pedido) {
  if (pedido?.para_llevar || pedido?.numero_mesa === 99) {
    return "Para llevar";
  }
  return `Mesa ${pedido?.numero_mesa ?? "—"}`;
}

export function buildComandaTicket({ pedido, lineas, usuario }) {
  const enc = encoder();
  const paraLlevar = pedido?.para_llevar || pedido?.numero_mesa === 99;
  const hora = new Date().toLocaleTimeString("es-MX", {
    hour: "2-digit",
    minute: "2-digit",
  });

  enc
    .align("center")
    .bold(true)
    .line("COMANDA COCINA")
    .bold(false)
    .newline()
    .align("left");

  if (paraLlevar) {
    enc.bold(true).line("PARA LLEVAR").bold(false);
  } else {
    enc.line(`Mesa: ${pedido?.numero_mesa}`);
  }
  enc.line(`Pedido: #${pedido?.id_pedido ?? "—"}`).line(`Hora: ${hora}`);

  if (usuario?.nombre) {
    enc.line(`Mesero: ${usuario.nombre}`);
  }

  enc.line("-".repeat(WIDTH)).newline();

  for (const item of lineas) {
    enc.bold(true).line(`${item.cantidad} x ${item.nombre_producto}`).bold(false);
    for (const extra of lineExtras(item.extras)) {
      enc.line(extra);
    }
    if (item.nombre_promocion) {
      enc.line(`  Promo: ${item.nombre_promocion}`);
    }
    if (item.comentario) {
      enc.line(`  * ${item.comentario}`);
    }
    enc.newline();
  }

  enc.align("center").line("---").newline().cut();

  return enc.encode();
}

/** Precuenta: sin forma de pago, folio ni puntos. */
export function buildPrecuentaTicket({ pedido, usuario, subtotal, descuento, total }) {
  const enc = encoder();
  appendCoffeeSongHeader(enc);

  enc
    .align("center")
    .bold(true)
    .line("PRECUENTA")
    .bold(false)
    .newline()
    .line(mesaOrigenLabel(pedido))
    .line(`Pedido #${pedido?.id_pedido ?? "—"}`)
    .line(
      new Date().toLocaleString("es-MX", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    )
    .align("left")
    .line("-".repeat(WIDTH))
    .newline();

  const lineas = pedido?.lineas ?? [];
  for (const item of lineas) {
    const sub = Number(item.cantidad) * Number(item.precio_unitario);
    enc.line(`${item.cantidad} x ${item.nombre_producto}`);
    enc.line(`   $${sub.toFixed(2)}`);
    for (const extra of lineExtras(item.extras)) {
      enc.line(extra);
    }
    if (item.nombre_promocion) {
      enc.line(`  Promo: ${item.nombre_promocion}`);
    }
    if (item.comentario) {
      enc.line(`  * ${item.comentario}`);
    }
  }

  enc.line("-".repeat(WIDTH));
  if (subtotal != null && descuento > 0) {
    enc.line(`Subtotal: $${Number(subtotal).toFixed(2)}`);
    enc.line(`Descuento: -$${Number(descuento).toFixed(2)}`);
  }
  enc.bold(true).line(`TOTAL: $${Number(total ?? 0).toFixed(2)}`).bold(false);
  enc
    .newline()
    .align("center")
    .bold(true)
    .line("PENDIENTE DE PAGO")
    .bold(false);

  if (usuario?.nombre) {
    enc.align("left").line(`Atendio: ${usuario.nombre}`);
  }

  enc.newline().align("center").line("---").newline().cut();
  return enc.encode();
}

export function buildCobroTicket({
  venta,
  pedido,
  usuario,
  clienteNombre,
  montoRecibido,
  cambio,
}) {
  const enc = encoder();
  const mesaLabel = venta?.para_llevar || venta?.numero_mesa === 99
    ? "Para llevar"
    : `Mesa ${venta?.numero_mesa ?? pedido?.numero_mesa}`;
  const fecha = new Date(venta?.fecha_hora || Date.now()).toLocaleString("es-MX", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  appendCoffeeSongHeader(enc);

  enc
    .align("center")
    .bold(true)
    .line("TICKET DE VENTA")
    .bold(false)
    .newline()
    .line(`Folio #${venta?.id_venta ?? "—"}`)
    .line(mesaLabel)
    .line(fecha)
    .align("left")
    .line("-".repeat(WIDTH))
    .newline();

  const lineas = pedido?.lineas ?? [];
  for (const item of lineas) {
    const sub = Number(item.cantidad) * Number(item.precio_unitario);
    enc.line(`${item.cantidad} x ${item.nombre_producto}`);
    enc.line(`   $${sub.toFixed(2)}`);
    for (const extra of lineExtras(item.extras)) {
      enc.line(extra);
    }
    if (item.comentario) {
      enc.line(`  * ${item.comentario}`);
    }
  }

  enc.line("-".repeat(WIDTH));
  enc.bold(true).line(`TOTAL: $${Number(venta?.total ?? 0).toFixed(2)}`).bold(false);
  enc.line(`Pago: ${etiquetaFormaPago(venta?.forma_pago)}`);
  if (
    venta?.forma_pago === "EFECTIVO" &&
    montoRecibido != null &&
    !isNaN(Number(montoRecibido))
  ) {
    enc.line(`Recibido: $${Number(montoRecibido).toFixed(2)}`);
    if (cambio != null && !isNaN(Number(cambio))) {
      enc.bold(true).line(`Cambio: $${Number(cambio).toFixed(2)}`).bold(false);
    }
  }

  if (usuario?.nombre) {
    enc.line(`Cajero: ${usuario.nombre}`);
  }
  if (clienteNombre) {
    enc.line(`Cliente: ${clienteNombre}`);
  }
  if (venta?.puntos_generados > 0) {
    enc.line(`Puntos: +${venta.puntos_generados}`);
  }

  enc
    .newline()
    .align("center")
    .line("--------------------------------")
    .bold(true)
    .line("Gracias por tu visita")
    .bold(false)
    .line("Te esperamos pronto")
    .line(BRAND_NAME)
    .newline()
    .cut();

  return enc.encode();
}
