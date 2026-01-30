import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    // Đã xóa phần proxy để tránh xung đột với vercel dev
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})