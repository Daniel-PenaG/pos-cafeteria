import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const NATIVE = /\b(window\.)?(alert|confirm)\s*\(/;

const FILES = [
  "pages/Ventas.jsx",
  "pages/Comandera.jsx",
  "components/CancelacionLineaModal.jsx",
];

describe("sin diálogos nativos en flujos operativos", () => {
  for (const rel of FILES) {
    it(`${rel} no usa alert/confirm`, () => {
      const src = readFileSync(path.join(root, rel), "utf8");
      assert.doesNotMatch(src, NATIVE, `Encontrado alert/confirm nativo en ${rel}`);
    });
  }
});
