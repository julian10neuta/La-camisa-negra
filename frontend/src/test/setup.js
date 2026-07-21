// src/test/setup.js
// Se ejecuta antes de cada archivo de test (lo configura vitest.config.js).
// Registra los matchers de @testing-library/jest-dom en el `expect` de Vitest,
// para poder escribir aserciones legibles sobre el DOM como
// `expect(el).toBeInTheDocument()` o `.toHaveTextContent(...)`.
import "@testing-library/jest-dom/vitest";
