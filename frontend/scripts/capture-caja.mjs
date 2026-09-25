/**
 * Capturas de caja (Fase 3A) contra API y preview locales.
 *
 * Requiere variables de entorno. Falla si faltan o si el host no es local.
 *
 *   $env:PREVIEW_URL="http://127.0.0.1:5176"
 *   $env:API_URL="http://127.0.0.1:18081"
 *   $env:CAPTURE_LOGIN="..."
 *   $env:CAPTURE_PASSWORD="..."
 *   npm run capture:caja
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../../docs/screenshots/caja");

function requireEnv(name) {
  const value = (process.env[name] || "").trim();
  if (!value) {
    throw new Error(`Falta ${name}. No se usan credenciales por defecto.`);
  }
  return value;
}

function assertLocalUrl(label, raw) {
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`${label} no es una URL válida`);
  }
  const host = (parsed.hostname || "").toLowerCase();
  if (!["127.0.0.1", "localhost", "::1"].includes(host)) {
    throw new Error(`${label} debe ser localhost. No se captura contra hosts remotos.`);
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(`${label} debe usar http(s)`);
  }
  return raw.replace(/\/$/, "");
}

const BASE = assertLocalUrl("PREVIEW_URL", requireEnv("PREVIEW_URL"));
const API = assertLocalUrl("API_URL", requireEnv("API_URL"));
const USER = requireEnv("CAPTURE_LOGIN");
const PASS = requireEnv("CAPTURE_PASSWORD");

async function api(method, pathName, token, body) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${pathName}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const raw = await res.text();
  let parsed = {};
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = { detail: "respuesta no JSON" };
    }
  }
  return { status: res.status, body: parsed };
}

async function loginApi() {
  const { status, body } = await api("POST", "/auth/login", null, {
    usuario_login: USER,
    password: PASS,
  });
  if (status !== 200 || !body.access_token) {
    throw new Error(`Login de captura falló (${status}).`);
  }
  return body;
}

async function closeIfOpen(token, declarado) {
  const mine = await api("GET", "/caja/sesion", token);
  const sesion = mine.body?.sesion;
  if (!sesion || !["ABIERTA", "EN_ARQUEO"].includes(sesion.estado)) return null;
  if (sesion.estado === "ABIERTA") {
    const arq = await api("POST", "/caja/arqueo", token);
    if (arq.status !== 200) {
      throw new Error(`No se pudo iniciar arqueo (${arq.status}).`);
    }
  }
  const fondo = Number(sesion.fondo_inicial || 0);
  const efectivo = declarado === undefined ? fondo : Number(declarado);
  const { status, body } = await api("POST", "/caja/cerrar", token, {
    captura_directa: true,
    declarado_efectivo: efectivo,
    declarado_transferencia: 0,
    declarado_tarjeta: 0,
    observacion: efectivo === fondo ? "cierre de captura local" : "faltante de captura",
    forzar: true,
  });
  if (status !== 200) {
    throw new Error(`No se pudo cerrar la sesión (${status}).`);
  }
  return body;
}

async function terminalLibre(token) {
  const terms = ["CAJA-1", "CAJA-2", "CAJA-3", "BARRA"];
  const lista = await api("GET", "/caja/sesiones", token);
  const ocupadas = new Set(
    (Array.isArray(lista.body) ? lista.body : [])
      .filter((s) => ["ABIERTA", "EN_ARQUEO"].includes(s.estado))
      .map((s) => s.terminal)
  );
  const libre = terms.find((t) => !ocupadas.has(t));
  if (!libre) {
    throw new Error("No hay terminal libre para capturar. Cierra una sesión activa.");
  }
  return libre;
}

async function shot(page, rel) {
  const dest = path.join(OUT, rel);
  await mkdir(path.dirname(dest), { recursive: true });
  await page.screenshot({ path: dest, fullPage: true });
  console.log(`ok ${rel}`);
}

async function gotoCaja(page) {
  await page.goto(`${BASE}/cierre-caja`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
}

async function main() {
  const auth = await loginApi();
  const token = auth.access_token;
  await closeIfOpen(token);
  const terminal = await terminalLibre(token);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  page.on("dialog", (dialog) => dialog.accept());
  await page.addInitScript(
    ({ stored }) => {
      localStorage.setItem("pos_cafeteria_auth", stored);
    },
    { stored: JSON.stringify({ token, user: auth.user }) }
  );

  await gotoCaja(page);
  await page.getByRole("heading", { name: /Abrir caja/i }).waitFor({ timeout: 15000 });
  await shot(page, "390x844/caja-sin-abrir.png");

  await page.locator("#fondo-inicial").fill("150");
  await page.locator("#terminal-caja").selectOption(terminal);
  await page.locator("#obs-apertura").fill("Captura local");
  await shot(page, "390x844/modal-apertura.png");

  await page.getByRole("button", { name: /Abrir caja/i }).click();
  await page.getByRole("button", { name: /Iniciar arqueo/i }).waitFor({ timeout: 15000 });
  await shot(page, "390x844/caja-abierta.png");

  const completarArqueo = async (efectivo, obs) => {
    const directa = page.locator(".caja-check input[type=checkbox]").first();
    if (!(await directa.isChecked())) {
      await directa.check();
    }
    await page.locator("#efectivo-directo").fill(String(efectivo));
    await page.locator("#decl-trans").fill("0");
    await page.locator("#decl-term").fill("0");
    if (obs) {
      await page.locator("#obs-cierre").fill(obs);
    }
    if (await page.getByText(/Forzar cierre con pedidos abiertos/i).count()) {
      await page.locator(".caja-check input[type=checkbox]").last().check();
    }
    await page.getByRole("button", { name: /Confirmar arqueo y cerrar/i }).click();
    await page.getByRole("heading", { name: /Conciliación/i }).waitFor({ timeout: 15000 });
  };

  await page.getByRole("button", { name: /Iniciar arqueo/i }).click();
  await page.getByRole("heading", { name: /Arqueo ciego/i }).waitFor({ timeout: 15000 });
  await shot(page, "390x844/arqueo-ciego.png");
  await completarArqueo(150, "");
  await shot(page, "390x844/resultado-conciliado.png");

  await gotoCaja(page);
  await page.getByRole("heading", { name: /Abrir caja/i }).waitFor({ timeout: 15000 });
  await page.locator("#fondo-inicial").fill("80");
  await page.locator("#terminal-caja").selectOption(terminal);
  await page.getByRole("button", { name: /Abrir caja/i }).click();
  await page.getByRole("button", { name: /Iniciar arqueo/i }).waitFor({ timeout: 15000 });
  await page.getByRole("button", { name: /Iniciar arqueo/i }).click();
  await page.getByRole("heading", { name: /Arqueo ciego/i }).waitFor({ timeout: 15000 });
  await completarArqueo(50, "faltante de captura");
  await shot(page, "390x844/resultado-diferencia.png");

  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(`${BASE}/cierres-dia`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  await shot(page, "1366x768/vista-admin.png");

  await browser.close();
}

main().catch((err) => {
  console.error(err.message || "captura falló");
  process.exit(1);
});
