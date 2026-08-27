import QRCode from "qrcode";

/** Código de fidelidad: CAFE- + 6 hex (ej. CAFE-A1B2C3) */
const CODIGO_RE = /CAFE-[A-F0-9]{6}/i;

export function parseCodigoFidelidad(raw) {
  if (!raw || typeof raw !== "string") return null;
  const text = raw.trim();
  const match = text.match(CODIGO_RE);
  if (match) return match[0].toUpperCase();
  const upper = text.toUpperCase();
  if (upper.startsWith("CAFE-")) {
    const parte = upper.split(/[\s,?&=#]/)[0];
    if (parte.length >= 10) return parte.slice(0, 11);
  }
  return null;
}

export async function generateQrDataUrl(text, size = 220) {
  if (!text) return "";
  return QRCode.toDataURL(String(text), {
    width: size,
    margin: 2,
    errorCorrectionLevel: "M",
  });
}
