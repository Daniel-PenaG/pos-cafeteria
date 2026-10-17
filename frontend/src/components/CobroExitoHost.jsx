import { flushSync } from "react-dom";
import CobroExitoModal from "./CobroExitoModal";
import { useCobroExitoStore } from "../store/cobroExitoStore";

function ocultarOverlayCobroSync() {
  const box = document.querySelector('[data-nav-cobro-resumen="visible"]');
  const overlay = box?.closest(".modal-overlay");
  if (overlay) {
    overlay.style.display = "none";
    overlay.style.pointerEvents = "none";
  }
}

/** Resumen post-cobro fuera de Ventas para no re-renderizar el carrito al cerrar. */
export default function CobroExitoHost() {
  const open = useCobroExitoStore((s) => s.open);
  const resumen = useCobroExitoStore((s) => s.resumen);
  const closeImmediate = useCobroExitoStore((s) => s.closeImmediate);
  const clearResumen = useCobroExitoStore((s) => s.clearResumen);

  return (
    <CobroExitoModal
      open={Boolean(open && resumen)}
      resumen={resumen}
      onClose={() => {
        if (import.meta.env.MODE === "e2e") {
          window.__posE2e?.markCobroClose?.("close_click");
        }
        ocultarOverlayCobroSync();
        if (import.meta.env.MODE === "e2e") {
          window.__posE2e?.markCobroClose?.("modal_hidden");
        }
        flushSync(() => {
          closeImmediate();
        });
        requestAnimationFrame(() => {
          clearResumen();
          requestAnimationFrame(() => {
            if (import.meta.env.MODE === "e2e") {
              window.__posE2e?.markCobroClose?.("cleanup_done");
            }
          });
        });
      }}
    />
  );
}
