import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), ['BACKEND_PROXY_TARGET']);
  if (!env.BACKEND_PROXY_TARGET && mode === 'development') {
    throw new Error('Set BACKEND_PROXY_TARGET in .env.development');
  }

  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
    server: {
      proxy: env.BACKEND_PROXY_TARGET
        ? {
            '/api': { target: env.BACKEND_PROXY_TARGET, changeOrigin: true },
            '/health': { target: env.BACKEND_PROXY_TARGET, changeOrigin: true },
          }
        : undefined,
    },
  };
});
