import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Components are styled with plain CSS custom properties; behaviour under
    // test never depends on the stylesheet, so skip processing it.
    css: false,
    // No `globals: true` on purpose -- each test imports describe/it/expect
    // from vitest explicitly, which keeps ESLint (no vitest env, and
    // --max-warnings 0) and tsc happy without touching either config.
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
