import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), ['BACKEND_', 'API_']);
  if (mode === 'development' && !env.BACKEND_PROXY_TARGET) throw new Error('Set BACKEND_PROXY_TARGET in frontend/.env');

  return {
    plugins: [react(), tailwindcss()],
    define: { 'import.meta.env.API_BASE_URL': JSON.stringify(env.API_BASE_URL || '/api') },
    resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
    server: {
      proxy: env.BACKEND_PROXY_TARGET
        ? {
            '/api': { target: env.BACKEND_PROXY_TARGET, changeOrigin: true, ws: true },
            '/health': { target: env.BACKEND_PROXY_TARGET, changeOrigin: true },
          }
        : undefined,
    },
  };
});
