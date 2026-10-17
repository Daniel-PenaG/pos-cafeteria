/** Estado de navegación Ventas (misma sesión, distinto usuario). */

const sessions = new Map();

function keyFor(userId, modoParaLlevar) {
  return `${userId}:${modoParaLlevar ? "llevar" : "mesa"}`;
}

export function readVentasSession(userId, modoParaLlevar) {
  if (!userId) return null;
  return sessions.get(keyFor(userId, modoParaLlevar)) || null;
}

export function writeVentasSession(userId, modoParaLlevar, snapshot) {
  if (!userId) return;
  sessions.set(keyFor(userId, modoParaLlevar), {
    ...snapshot,
    savedAt: Date.now(),
  });
}

export function clearVentasSessionsForUser(userId) {
  if (!userId) return;
  for (const k of sessions.keys()) {
    if (k.startsWith(`${userId}:`)) sessions.delete(k);
  }
}

export function clearAllVentasSessions() {
  sessions.clear();
}
