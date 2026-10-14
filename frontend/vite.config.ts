import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), ['BACKEND_', 'API_']);
  if (mode === 'development') {
    const missing = ['BACKEND_PROXY_TARGET', 'BACKEND_API_KEY'].filter((name) => !env[name]);
    if (missing.length) throw new Error(`Set ${missing.join(' and ')} in frontend/.env`);
  }

  // The proxy adds the API key server side so it never ships in the browser bundle.
  const apiHeaders = env.BACKEND_API_KEY ? { 'X-API-Key': env.BACKEND_API_KEY } : undefined;

  return {
    plugins: [react(), tailwindcss()],
    define: { 'import.meta.env.API_BASE_URL': JSON.stringify(env.API_BASE_URL || '/api') },
    resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
    server: {
      proxy: env.BACKEND_PROXY_TARGET
        ? {
            '/api': { target: env.BACKEND_PROXY_TARGET, changeOrigin: true, headers: apiHeaders },
            '/health': { target: env.BACKEND_PROXY_TARGET, changeOrigin: true },
          }
        : undefined,
    },
  };
});
