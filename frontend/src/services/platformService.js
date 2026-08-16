import { Capacitor } from "@capacitor/core";

export function isNativeApp() {
  return Capacitor.isNativePlatform();
}

export function isAndroidApp() {
  return Capacitor.getPlatform() === "android";
}
