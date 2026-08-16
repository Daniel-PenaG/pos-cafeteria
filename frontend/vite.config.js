import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  // Amplify usa '/'; la APK Capacitor (--mode capacitor) necesita rutas relativas.
  base: mode === 'capacitor' ? './' : '/',
}))
