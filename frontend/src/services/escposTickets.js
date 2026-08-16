import ThermalPrinterEncoder from "thermal-printer-encoder";

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

function formatFormaPago(forma) {
  const map = {
    EFECTIVO: "Efectivo",
    TARJETA: "Tarjeta",
    TRANSFERENCIA: "Transferencia",
  };
  return map[forma] || forma;
}

export function buildComandaTicket({ pedido, lineas, usuario }) {
  const enc = encoder();
  const mesa = pedido?.numero_mesa;
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
    .align("left")
    .line(`Mesa: ${mesa}`)
    .line(`Pedido: #${pedido?.id_pedido ?? "—"}`)
    .line(`Hora: ${hora}`);

  if (usuario?.nombre) {
    enc.line(`Mesero: ${usuario.nombre}`);
  }

  enc.line("-".repeat(WIDTH)).newline();

  for (const item of lineas) {
    enc.bold(true).line(`${item.cantidad} x ${item.nombre_producto}`).bold(false);
    for (const extra of lineExtras(item.extras)) {
      enc.line(extra);
    }
    if (item.comentario) {
      enc.line(`  * ${item.comentario}`);
    }
    enc.newline();
  }

  enc.align("center").line("---").newline().cut();

  return enc.encode();
}

export function buildCobroTicket({
  venta,
  pedido,
  usuario,
  clienteNombre,
}) {
  const enc = encoder();
  const mesa = venta?.numero_mesa ?? pedido?.numero_mesa;
  const mesaLabel =
    venta?.para_llevar || mesa === 99 ? "Para llevar" : `Mesa ${mesa}`;
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
  enc.line(`Pago: ${formatFormaPago(venta?.forma_pago)}`);

  if (usuario?.nombre) {
    enc.line(`Cajero: ${usuario.nombre}`);
  }
  if (clienteNombre) {
    enc.line(`Cliente: ${clienteNombre}`);
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
