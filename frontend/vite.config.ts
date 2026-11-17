/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

declare const process: { env: Record<string, string | undefined> }; // Node global; avoids pulling in @types/node

// `/api/*` is proxied to FastAPI so the browser sees one origin (first-party
// session cookie, no CORS). Production does the same with a Vercel rewrite.
const API_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
  preview: {
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
