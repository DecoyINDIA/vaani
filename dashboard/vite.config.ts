import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Build output is consumed by FastAPI static mount (app/main.py -> dashboard/dist).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: { outDir: "dist" },
  server: {
    // Dev proxy so the SPA can call the FastAPI owner API without CORS.
    proxy: { "/api": "http://localhost:8000" },
  },
});
