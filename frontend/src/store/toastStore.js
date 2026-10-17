import { create } from "zustand";

let seq = 0;

export const useToastStore = create((set) => ({
  toasts: [],
  push(message, variant = "info", { durationMs = 4500, dedupeKey } = {}) {
    const id = dedupeKey || `t-${++seq}`;
    set((state) => {
      if (dedupeKey && state.toasts.some((t) => t.dedupeKey === dedupeKey)) {
        return state;
      }
      const next = [
        ...state.toasts,
        { id, message, variant, dedupeKey, createdAt: Date.now() },
      ].slice(-5);
      if (durationMs > 0) {
        window.setTimeout(() => {
          useToastStore.getState().dismiss(id);
        }, durationMs);
      }
      return { toasts: next };
    });
    return id;
  },
  dismiss(id) {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
  clear() {
    set({ toasts: [] });
  },
}));

export function toastSuccess(message, opts) {
  return useToastStore.getState().push(message, "success", opts);
}

export function toastError(message, opts) {
  return useToastStore.getState().push(message, "error", { durationMs: 7000, ...opts });
}

export function toastInfo(message, opts) {
  return useToastStore.getState().push(message, "info", opts);
}
