/**

 * Solo importado cuando import.meta.env.MODE === "e2e".

 * Expone utilidades de medición sin credenciales ni tokens.

 */

import { clearOperationalSession } from "../cache/sessionCleanup";

import {

  clearAllOperationalCaches,

  invalidateCatalogCache,

} from "../cache/operationalCaches";

import { clearAllVentasSessions } from "../store/ventasNavStore";



let listoMarks = [];

let listoLongTasks = [];

let cobroCloseMarks = [];

let listoSampleHandlers = null;

let listoPerfObserver = null;



function markListoPhase(phase, extra = {}) {

  listoMarks.push({ phase, t: performance.now(), ...extra });

}



function disarmListoSample() {

  if (listoSampleHandlers) {

    document.removeEventListener("pointerdown", listoSampleHandlers.onPointerDown, true);

    document.removeEventListener("click", listoSampleHandlers.onClick, true);

    listoSampleHandlers = null;

  }

  if (listoPerfObserver) {

    try {

      listoPerfObserver.disconnect();

    } catch {

      /* ignore */

    }

    listoPerfObserver = null;

  }

}



function armListoSample() {

  disarmListoSample();

  listoMarks = [];

  listoLongTasks = [];



  const onPointerDown = (ev) => {

    const btn = ev.target?.closest?.("[data-nav-listo-btn]");

    if (!btn) return;

    if (listoMarks.some((m) => m.phase === "pointerdown")) return;

    markListoPhase("pointerdown", { eventTs: ev.timeStamp });

  };

  const onClick = (ev) => {

    const btn = ev.target?.closest?.("[data-nav-listo-btn]");

    if (!btn) return;

    if (listoMarks.some((m) => m.phase === "click")) return;

    markListoPhase("click", { eventTs: ev.timeStamp });

  };

  document.addEventListener("pointerdown", onPointerDown, true);

  document.addEventListener("click", onClick, true);

  listoSampleHandlers = { onPointerDown, onClick };



  if (typeof PerformanceObserver !== "undefined") {

    try {

      listoPerfObserver = new PerformanceObserver((list) => {

        for (const entry of list.getEntries()) {

          listoLongTasks.push({

            startTime: entry.startTime,

            duration: entry.duration,

          });

        }

      });

      listoPerfObserver.observe({ type: "longtask", buffered: true });

    } catch {

      /* longtask no disponible */

    }

  }

}



function phaseTime(phase) {

  const hit = listoMarks.find((m) => m.phase === phase);

  return hit?.t;

}



function readListoPhaseDeltasMs() {

  const pd = phaseTime("pointerdown");

  const clk = phaseTime("click");

  const h = phaseTime("handler_start");

  const dom = phaseTime("dom_syncing_visible") ?? phaseTime("visual_local");

  const r0 = phaseTime("request_start");

  const r1 = phaseTime("response_received");

  const end = phaseTime("reconcile_done") ?? r1 ?? r0 ?? dom;



  const anchorPd = pd ?? clk ?? h ?? performance.now();

  const anchorClk = clk ?? pd ?? h ?? anchorPd;



  const safe = (a, b) => (a != null && b != null ? Math.max(0, b - a) : null);



  const deltas = {

    pointerdown_a_handler: safe(pd, h),

    click_a_handler: safe(clk, h),

    handler_a_dom_optimista: safe(h, dom),

    pointerdown_a_dom_optimista: safe(pd, dom),

    click_a_dom_optimista: safe(clk, dom),

    dom_optimista_a_inicio_post: safe(dom, r0),

    request_a_respuesta_http: safe(r0, r1),

    respuesta_a_reconciliacion: safe(r1, end),

    total: safe(anchorPd, end),

    raf_after_paint_from_handler: safe(h, phaseTime("raf_after_paint")),

    // Compat / desglose histórico (no usar para objetivos de feedback visual)

    click_a_handler_legacy: safe(anchorClk, h),

    handler_a_visual_local: safe(h, phaseTime("visual_local")),

    click_a_request_inicio: safe(anchorClk, r0),

  };



  disarmListoSample();

  listoMarks = [];



  return deltas;

}



export function registerPosE2eHooks() {

  if (import.meta.env.MODE !== "e2e") return;

  window.__posE2e = Object.freeze({

    clearOperationalSession,

    clearAllOperationalCaches,

    clearAllVentasSessions,

    invalidateCatalogCache,

    clearListoMarks() {

      listoMarks = [];

      listoLongTasks = [];

      disarmListoSample();

    },

    markListo(phase) {

      markListoPhase(phase);

    },

    takeListoMarks() {

      const copy = listoMarks;

      listoMarks = [];

      return copy;

    },

    armListoSample,

    armListoClickAnchor: armListoSample,

    takeListoLongTasks() {

      const copy = listoLongTasks;

      listoLongTasks = [];

      return copy;

    },

    readListoPhaseDeltasMs,

    clearCobroCloseMarks() {

      cobroCloseMarks = [];

    },

    markCobroClose(phase) {

      cobroCloseMarks.push({ phase, t: performance.now() });

    },

    takeCobroCloseMarks() {

      const copy = cobroCloseMarks;

      cobroCloseMarks = [];

      return copy;

    },

    pulseCatalogRevalidatingBanner() {

      invalidateCatalogCache();

      window.dispatchEvent(new CustomEvent("pos:e2e-catalog-swr-probe"));

    },

  });

}



registerPosE2eHooks();
