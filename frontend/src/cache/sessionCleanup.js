import { clearAllOperationalCaches } from "./operationalCaches";
import { clearAllVentasSessions } from "../store/ventasNavStore";
import { useToastStore } from "../store/toastStore";

let operationalSessionEpoch = 0;

export function getOperationalSessionEpoch() {
  return operationalSessionEpoch;
}

export function clearOperationalSession() {
  operationalSessionEpoch += 1;
  clearAllOperationalCaches();
  clearAllVentasSessions();
  useToastStore.getState().clear();
}
