import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, the React app runs on :5173 and proxies /api to the FastAPI backend on :8000.
// In prod, FastAPI serves the built SPA, so /api is same-origin and the proxy is unused.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist" },
});
