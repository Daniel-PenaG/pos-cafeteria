const MAC_KEY = "pos_printer_mac";
const NAME_KEY = "pos_printer_name";

export function getSavedPrinter() {
  const address = localStorage.getItem(MAC_KEY);
  if (!address) return null;
  return {
    address,
    name: localStorage.getItem(NAME_KEY) || address,
  };
}

export function savePrinter(device) {
  if (!device?.address) return;
  localStorage.setItem(MAC_KEY, device.address);
  localStorage.setItem(NAME_KEY, device.name || device.alias || device.address);
}

export function clearSavedPrinter() {
  localStorage.removeItem(MAC_KEY);
  localStorage.removeItem(NAME_KEY);
}
