import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    open: true,
    cors: true,
    host: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    target: "es2020",
    outDir: "dist",
    sourcemap: false,
    minify: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@tanstack/react-query")) return "query";
          if (id.includes("@radix-ui")) return "ui";
          if (id.includes("/react-router") || id.includes("/react-dom/") || /\/react\//.test(id)) {
            return "vendor";
          }
          return undefined;
        },
      },
    },
  },
  preview: {
    port: 4173,
    open: true,
  },
});
