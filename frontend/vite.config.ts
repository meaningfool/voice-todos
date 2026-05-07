/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const frontendPort = Number(process.env.FRONTEND_PORT ?? "5173");
const backendPort = Number(process.env.BACKEND_PORT ?? "8000");
const cloudflarePort = Number(process.env.CLOUDFLARE_PORT ?? "8788");

function resolveWsBackendTarget() {
  const wsBackend = process.env.WS_BACKEND ?? "fastapi";

  if (wsBackend === "fastapi") {
    return `ws://localhost:${backendPort}`;
  }

  if (wsBackend === "cloudflare") {
    return `ws://localhost:${cloudflarePort}`;
  }

  throw new Error(`Unsupported WS_BACKEND: ${wsBackend}`);
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
  server: {
    port: frontendPort,
    strictPort: true,
    proxy: {
      "/ws": {
        target: resolveWsBackendTarget(),
        ws: true,
      },
    },
  },
});
