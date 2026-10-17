import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { describe, it } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const dist = path.join(frontendRoot, "dist");

function readAllJs() {
  const assets = path.join(dist, "assets");
  return readdirSync(assets)
    .filter((f) => f.endsWith(".js"))
    .map((f) => readFileSync(path.join(assets, f), "utf8"))
    .join("\n");
}

function readPosE2eChunk() {
  const assets = path.join(dist, "assets");
  const files = readdirSync(assets).filter((f) => f.endsWith(".js"));
  const hit =
    files.find((f) => /^registerPosE2e-.*\.js$/.test(f)) ||
    files.find((f) => readFileSync(path.join(assets, f), "utf8").includes("registerPosE2e"));
  assert.ok(hit, "falta chunk registerPosE2e en build e2e");
  return readFileSync(path.join(assets, hit), "utf8");
}

function build(mode) {
  const env = { ...process.env, VITE_API_URL: "http://127.0.0.1:8000" };
  execSync(`npm run build -- --mode ${mode}`, {
    cwd: frontendRoot,
    stdio: "pipe",
    env,
  });
}

function assertBundleLimpio(label, bundle) {
  assert.doesNotMatch(bundle, /__posE2e/);
  assert.doesNotMatch(bundle, /registerPosE2e/);
  assert.doesNotMatch(bundle, /E2E_CREDS_FILE/);
  assert.doesNotMatch(bundle, /CAPTURE_PASSWORD/);
}

describe("window.__posE2e en builds", () => {
  it("modo e2e incluye registerPosE2e / __posE2e", () => {
    build("e2e");
    const e2eChunk = readPosE2eChunk();
    assert.match(e2eChunk, /__posE2e/);
    assert.match(e2eChunk, /registerPosE2e/);
    assert.doesNotMatch(e2eChunk, /Authorization/i);
    assert.doesNotMatch(e2eChunk, /CAPTURE_PASSWORD/);
    assert.doesNotMatch(e2eChunk, /access_token/);
    assert.doesNotMatch(e2eChunk, /password/i);
  });

  it("modo production no expone __posE2e", () => {
    build("production");
    assertBundleLimpio("production", readAllJs());
  });

  it("modo capacitor no expone __posE2e", () => {
    build("capacitor");
    assertBundleLimpio("capacitor", readAllJs());
  });
});
