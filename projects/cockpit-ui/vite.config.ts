import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { target: "es2020", outDir: "dist" },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
