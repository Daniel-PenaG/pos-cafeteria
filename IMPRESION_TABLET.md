# Impresión Bluetooth en tablet (Capacitor)

La **web en Amplify no cambia**: sigue desplegándose con `npm run build` como siempre.

La **app Android** es el mismo frontend empaquetado, con impresión Bluetooth para impresoras ESC/POS (MHT-P58D 58 mm).

## Qué imprime

| Evento | Ticket |
|--------|--------|
| **Confirmar pedido** (mesas) | Comanda cocina — sin precios |
| **Cobrar** (mesa o para llevar) | Ticket de venta — con total y pago |

En la **web** (navegador) no imprime; el flujo de ventas es igual.

## Requisitos

- Tablet **Huawei/Android** con la impresora **MHT-P58D** emparejada en Ajustes → Bluetooth (PIN habitual: `1234` o `0000`)
- [Android Studio](https://developer.android.com/studio) en tu PC para generar la APK
- URL de la API de producción (Elastic Beanstalk)

## Generar la APK (una vez)

```powershell
cd frontend

# Configura la API de producción (copia el example)
copy .env.capacitor.example .env.capacitor.local
# Edita .env.capacitor.local → VITE_API_URL=https://tu-api-real...

npm install
npm run build:android
npm run cap:open
```

En Android Studio: **Build → Build Bundle(s) / APK(s) → Build APK(s)**.

Instala el APK en la Huawei (AppGallery o archivo `.apk` manual).

## Uso en la tablet

1. Abre la app **Cafe POS** (no el navegador).
2. Inicia sesión (mismos usuarios que la web).
3. En **Ventas** → botón **Impresora** → elige la MHT-P58D emparejada → **Imprimir prueba**.
4. Opera normal: al **confirmar pedido** sale comanda; al **cobrar** sale ticket.

## Deploy web (Amplify) — sin cambios

```powershell
npm run build
```

No uses `--mode capacitor` para Amplify. El `base` de Vite sigue siendo `/` en builds normales.

## Estructura añadida

```
frontend/
  android/              ← proyecto Capacitor (APK)
  capacitor.config.json
  src/services/
    printerService.js   ← Bluetooth ESC/POS
    escposTickets.js    ← formato comanda/ticket
  src/components/
    PrinterSettings.jsx ← configurar impresora
```

## Problemas frecuentes

| Problema | Solución |
|----------|----------|
| No aparece la impresora | Emparejarla antes en Ajustes Android |
| Error de permisos Bluetooth | Aceptar permisos de la app; Android 12+ pide Bluetooth y ubicación |
| No imprime pero cobra bien | Revisar batería de la impresora y MAC guardada en Impresora |
| La web no imprime | Es normal; usa la APK en la tablet |
