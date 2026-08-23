import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const removeCrossorigin = () => ({
  name: "remove-crossorigin",
  transformIndexHtml(html) {
    return html.replace(/ crossorigin/g, "");
  },
});

export default defineConfig({
  base: "./",
  plugins: [react(), removeCrossorigin()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
