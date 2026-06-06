import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// @modelcontextprotocol/sdk v1.x uses Node.js stream internally,
// which needs polyfilling for browser builds.
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      stream: resolve(__dirname, "node_modules/stream-browserify"),
    },
  },
  optimizeDeps: {
    include: ["@modelcontextprotocol/sdk"],
  },
  build: {
    rollupOptions: {
      plugins: [
        {
          name: "fix-mcp-sdk",
          resolveId(source) {
            if (source === "stream") {
              return resolve(__dirname, "node_modules/stream-browserify/index.js");
            }
            return null;
          },
        },
      ],
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
