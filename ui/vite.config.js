import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/investigate': 'http://localhost:8085',
      '/investigations': 'http://localhost:8085',
      '/demo': 'http://localhost:8085',
      '/webhooks': 'http://localhost:8085',
      '/health': 'http://localhost:8085',
    },
  },
})
