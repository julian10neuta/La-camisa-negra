// vitest.config.js
// ----------------------------------------------------------------------------
// Configuración de los tests del frontend (Vitest). Vive APARTE del vite.config.js
// a propósito: hereda de él con mergeConfig (para reusar el plugin de React) pero
// NO lo modifica, así que `vite build` y `vite dev` quedan intactos. Vitest carga
// este archivo automáticamente y tiene prioridad sobre vite.config.js.
// ----------------------------------------------------------------------------
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config.js";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      // jsdom da un DOM falso (document, localStorage, window) para poder testear
      // los módulos que lo usan sin un navegador de verdad.
      environment: "jsdom",
      // `globals: true` = describe/it/expect disponibles sin importarlos, como en Jest.
      globals: true,
      // Registra los matchers de jest-dom (toBeInTheDocument, etc.) antes de cada test.
      setupFiles: "./src/test/setup.js",
      css: false,
      coverage: {
        provider: "v8",
        reporter: ["text", "html"],
        include: ["src/**/*.{js,jsx}"],
        // Se excluyen los puntos de entrada y el arranque del SDK: son cableado y
        // efectos, no lógica con ramas que valga la pena cubrir.
        exclude: ["src/main.jsx", "src/test/**", "**/*.config.js"],
      },
    },
  })
);
