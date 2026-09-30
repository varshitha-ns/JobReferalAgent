import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  build: {
    outDir: "dist",
    emptyOutDir: true,

    rollupOptions: {
      input: {
        popup: "index.html",
        content: "src/content.ts"
      },

      output: {
        entryFileNames: (chunk) => {
          if (chunk.name === "content") {
            return "content.js";
          }

          return "assets/[name].js";
        }
      }
    }
  }
});