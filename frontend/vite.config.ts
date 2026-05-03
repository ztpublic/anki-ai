import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  build: {
    outDir: path.resolve(__dirname, "../anki_ai/web"),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        index: path.resolve(__dirname, "index.html"),
        reviewer: path.resolve(__dirname, "src/reviewer.tsx"),
      },
    },
  },
});
