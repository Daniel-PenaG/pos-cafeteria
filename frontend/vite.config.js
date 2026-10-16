import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('.', import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, rootDir, '')
  const e2eApi = env.VITE_API_URL || 'http://127.0.0.1:8000'
  return {
    plugins: [react(), tailwindcss()],
    // Amplify usa '/'; la APK Capacitor (--mode capacitor) necesita rutas relativas.
    base: mode === 'capacitor' ? './' : '/',
    ...(mode === 'e2e'
      ? {
          define: {
            'import.meta.env.VITE_API_URL': JSON.stringify(e2eApi.replace(/\/$/, '')),
          },
        }
      : {}),
  }
})
