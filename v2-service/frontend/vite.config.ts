import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Бэкенд FastAPI поднимается на :8000. Проксируем API через dev-сервер Vite,
// чтобы фронт и бэк жили на одном origin — httpOnly-cookie авторизации тогда
// ходит без возни с CORS/SameSite.
const API_TARGET = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': API_TARGET,
      '/users': API_TARGET,
      '/projects': API_TARGET,
    },
  },
})
