// Valida el andamio de Vitest + React Testing Library + jsdom antes de escribir
// tests de verdad: que hay un DOM, que localStorage funciona, que se puede
// renderizar un componente y que los matchers de jest-dom están registrados.
import { render, screen } from "@testing-library/react";

it("jsdom da document y localStorage", () => {
  expect(typeof document).toBe("object");
  localStorage.setItem("k", "v");
  expect(localStorage.getItem("k")).toBe("v");
});

it("renderiza un componente y aplica los matchers de jest-dom", () => {
  render(<h1>Wavely</h1>);
  expect(screen.getByRole("heading")).toHaveTextContent("Wavely");
});
