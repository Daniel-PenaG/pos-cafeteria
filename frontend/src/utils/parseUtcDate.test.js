import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { elapsedSecondsUtc, parseUtcDate } from "./parseUtcDate.js";

describe("parseUtcDate", () => {
  it("trata ISO sin zona como UTC (sufijo Z implícito)", () => {
    const naive = parseUtcDate("2026-09-13T03:21:05");
    const zulu = parseUtcDate("2026-09-13T03:21:05Z");
    assert.ok(naive);
    assert.equal(naive.getTime(), zulu.getTime());
  });

  it("acepta offset explícito", () => {
    const d = parseUtcDate("2026-09-12T21:21:05-06:00");
    assert.equal(d.toISOString(), "2026-09-13T03:21:05.000Z");
  });
});

describe("elapsedSecondsUtc", () => {
  it("pedido reciente cerca de 0s", () => {
    const now = Date.UTC(2026, 8, 13, 3, 21, 5);
    const since = "2026-09-13T03:21:04Z";
    assert.equal(elapsedSecondsUtc(since, now), 1);
  });

  it("después de 65s muestra 65", () => {
    const now = Date.UTC(2026, 8, 13, 3, 22, 10);
    const since = "2026-09-13T03:21:05Z";
    assert.equal(elapsedSecondsUtc(since, now), 65);
  });

  it("recargar con la misma fecha conserva el tiempo", () => {
    const now = Date.UTC(2026, 8, 13, 3, 22, 10);
    const since = "2026-09-13T03:21:05Z";
    assert.equal(elapsedSecondsUtc(since, now), elapsedSecondsUtc(since, now));
  });

  it("nunca es negativo", () => {
    const now = Date.UTC(2026, 8, 13, 3, 21, 5);
    const future = "2026-09-13T04:00:00Z";
    assert.equal(elapsedSecondsUtc(future, now), 0);
  });

  it("usa respaldo del backend si no hay fecha", () => {
    assert.equal(elapsedSecondsUtc(null, Date.now(), 12), 12);
  });

  it("no usa zona del dispositivo: naive = UTC", () => {
    const now = Date.parse("2026-09-13T03:21:05Z");
    assert.equal(elapsedSecondsUtc("2026-09-13T03:21:05", now), 0);
  });
});
