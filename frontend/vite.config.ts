import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/clubs': 'http://localhost:8000',
      '/market': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/divisions': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
