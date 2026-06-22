import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies /api → the backend, so `npm run dev` works without relying
// on backend CORS. In dev we leave VITE_API_BASE empty (see .env.development) so
// the client calls same-origin /api/v1, which this proxy forwards.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_PROXY_TARGET || "http://136.109.192.193:8000";
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/api": { target, changeOrigin: true },
      },
    },
    preview: { port: 5173, host: true },
  };
});
