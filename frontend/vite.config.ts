/// <reference types="vitest/config" />
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Učilnica: the UI is served on 7686 and proxies /api to the FastAPI backend on 7687 (which only listens
// on 127.0.0.1). These ports don't clash with PitchDriven's 7676/7677. strictPort makes Vite fail loudly
// instead of silently moving to another port.
const API_TARGET = process.env.UCILNICA_API_URL ?? "http://127.0.0.1:7687";
const HOST = process.env.UCILNICA_HOST ?? "127.0.0.1";

const proxy = {
  "/api": { target: API_TARGET, changeOrigin: true },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    host: HOST,
    port: 7686,
    strictPort: true,
    proxy,
  },
  preview: {
    host: HOST,
    port: 7686,
    strictPort: true,
    proxy,
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
