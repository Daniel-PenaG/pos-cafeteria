import { isNativeApp } from "./platformService";
import { getSavedPrinter } from "./printerStorage";

export function canUseBluetoothPrinter() {
  return isNativeApp();
}

export async function listBluetoothPrinters() {
  if (!canUseBluetoothPrinter()) return [];

  const { EscPosPrinter } = await import("@fedejm/capacitor-esc-pos-printer");
  await EscPosPrinter.requestBluetoothEnable();
  const { devices } = await EscPosPrinter.getBluetoothPrinterDevices();
  return (devices || []).map((d) => ({
    address: d.address,
    name: d.alias || d.name || d.address,
  }));
}

export async function printEscPosBytes(bytes) {
  if (!canUseBluetoothPrinter()) {
    throw new Error("La impresión Bluetooth solo está disponible en la app Android.");
  }

  const saved = getSavedPrinter();
  if (!saved?.address) {
    throw new Error("Configura la impresora en Ajustes de impresión.");
  }

  const { EscPosPrinter, BluetoothPrinter } = await import(
    "@fedejm/capacitor-esc-pos-printer"
  );

  await EscPosPrinter.requestBluetoothEnable();

  const printer = new BluetoothPrinter(saved.address);
  try {
    await printer.link();
    await printer.connect();
    const data = bytes instanceof Uint8Array ? Array.from(bytes) : Array.from(bytes);
    await printer.send(data);
  } finally {
    try {
      await printer.disconnect();
    } catch {
      /* ignore */
    }
    try {
      await printer.dispose();
    } catch {
      /* ignore */
    }
  }
}

export async function printTicketSafely(buildFn, context) {
  if (!canUseBluetoothPrinter()) return { ok: true, skipped: true };

  try {
    const bytes = buildFn(context);
    await printEscPosBytes(bytes);
    return { ok: true, skipped: false };
  } catch (err) {
    console.error("Error de impresión:", err);
    return {
      ok: false,
      skipped: false,
      message: err?.message || "No se pudo imprimir",
    };
  }
}
