import { create } from "zustand";

export const useCobroExitoStore = create((set) => ({
  open: false,
  resumen: null,
  show(resumen) {
    set({ open: true, resumen });
  },
  closeImmediate() {
    set({ open: false });
  },
  clearResumen() {
    set({ resumen: null });
  },
}));

export function showCobroExitoResumen(resumen) {
  useCobroExitoStore.getState().show(resumen);
}
