// Tests del Context de ajustes: useSettings (leer/cambiar) y useDisplayName.
import { beforeEach, describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { SettingsProvider, useSettings, useDisplayName } from "./SettingsContext";

let api; // capturamos las funciones del context para llamarlas desde el test

function Harness() {
  api = useSettings();
  const displayName = useDisplayName();
  return (
    <div>
      <span data-testid="palette">{api.settings.palette}</span>
      <span data-testid="name">{displayName ?? "(sin nombre)"}</span>
    </div>
  );
}

beforeEach(() => localStorage.clear());

it("expone los ajustes por defecto y permite cambiarlos (persistiendo)", () => {
  render(<SettingsProvider><Harness /></SettingsProvider>);
  expect(screen.getByTestId("palette")).toHaveTextContent("default");

  act(() => api.set("palette", "tritanopia"));
  expect(screen.getByTestId("palette")).toHaveTextContent("tritanopia");
  // se guardó en localStorage
  expect(JSON.parse(localStorage.getItem("wavely:settings")).palette).toBe("tritanopia");
});

it("reset vuelve a los valores por defecto", () => {
  render(<SettingsProvider><Harness /></SettingsProvider>);
  act(() => api.set("palette", "protanopia"));
  act(() => api.reset());
  expect(screen.getByTestId("palette")).toHaveTextContent("default");
});

it("useDisplayName usa el apodo si lo hay, y si no el nombre de Spotify", () => {
  localStorage.setItem("user", JSON.stringify({ name: "Julian Spotify" }));
  render(<SettingsProvider><Harness /></SettingsProvider>);
  // sin apodo → nombre de Spotify guardado por el Callback
  expect(screen.getByTestId("name")).toHaveTextContent("Julian Spotify");
  // con apodo → gana el apodo
  act(() => api.set("nickname", "Juli"));
  expect(screen.getByTestId("name")).toHaveTextContent("Juli");
});
