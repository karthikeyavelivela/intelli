import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const api = process.env.VITE_API_PROXY || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    watch: { ignored: ["**/test-results/**", "**/playwright-report/**", "**/e2e/**", "**/e2e-docs/**", "**/coverage/**"] }, // Playwright artefacts must not trigger full reloads
    proxy: {
      "/api": { target: api, changeOrigin: true },
      "/docs": api,
      "/openapi.json": api,
      "/health": api,
    },
  },
  optimizeDeps: { exclude: ["jspdf"] },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      external: ["html2canvas", "dompurify", "canvg"], // optional jsPDF deps we never call
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
          motion: ["framer-motion"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
