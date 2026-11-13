import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    target: 'es2022',
  },
  server: {
    host: '127.0.0.1',
    fs: {
      allow: ['..'],
    },
  },
  resolve: {
    dedupe: ['vue'],
  },
})
