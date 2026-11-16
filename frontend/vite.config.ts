import { existsSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'
import vueDevTools from 'vite-plugin-vue-devtools'

const ROOT_ENV_MARKER = fileURLToPath(new URL('../.env', import.meta.url))
const ENV_DIR = existsSync(ROOT_ENV_MARKER) ? '..' : '.'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ENV_DIR, '')
  const proxyTarget =
    process.env.DEV_PROXY_TARGET || env.DEV_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    envDir: ENV_DIR,
    plugins: [vue(), vueDevTools(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: !proxyTarget.includes('host.docker.internal'),
        },
        '/media': {
          target: proxyTarget,
          changeOrigin: !proxyTarget.includes('host.docker.internal'),
        },
      },
    },
  }
})
