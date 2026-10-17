/**
 * Caché en memoria con TTL, deduplicación de requests en curso y aislamiento por clave de sesión.
 */
export function createResourceCache({ ttlMs, sessionKey = () => "anon" }) {
  let data = null;
  let expiresAt = 0;
  let inflight = null;
  let boundSession = null;
  let generation = 0;

  function reset() {
    generation += 1;
    data = null;
    expiresAt = 0;
    inflight = null;
  }

  function ensureSession() {
    const key = sessionKey();
    if (key !== boundSession) {
      reset();
      boundSession = key;
    }
    return key;
  }

  function peek(now = Date.now()) {
    ensureSession();
    if (!data || expiresAt <= now) return null;
    return data;
  }

  function invalidate() {
    ensureSession();
    expiresAt = 0;
  }

  function set(value, now = Date.now()) {
    ensureSession();
    data = value;
    expiresAt = now + ttlMs;
  }

  /**
   * @returns {Promise<{ value, fromCache: boolean, stale: boolean }>}
   */
  async function load(fetcher, { force = false, allowStale = true, now = Date.now() } = {}) {
    ensureSession();
    if (!force && data && expiresAt > now) {
      return { value: data, fromCache: true, stale: false };
    }
    if (!force && allowStale && data) {
      if (!inflight) {
        const gen = generation;
        inflight = Promise.resolve()
          .then(fetcher)
          .then((fresh) => {
            if (gen === generation) set(fresh, Date.now());
            return fresh;
          })
          .catch(() => {})
          .finally(() => {
            inflight = null;
          });
      }
      return { value: data, fromCache: true, stale: true };
    }
    if (inflight) {
      const fresh = await inflight;
      return { value: fresh, fromCache: !force, stale: false };
    }
    const gen = generation;
    inflight = Promise.resolve()
      .then(fetcher)
      .then((fresh) => {
        if (gen !== generation) return fresh;
        set(fresh, Date.now());
        return fresh;
      })
      .catch((err) => {
        throw err;
      })
      .finally(() => {
        inflight = null;
      });
    const fresh = await inflight;
    return { value: fresh, fromCache: false, stale: false };
  }

  return {
    load,
    peek,
    set,
    invalidate,
    reset,
    get generation() {
      return generation;
    },
  };
}
