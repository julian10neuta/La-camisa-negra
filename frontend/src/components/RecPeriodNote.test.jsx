// Tests del componente RecPeriodNote con React Testing Library. Al renderizarlo
// se ejercita también su lógica de fechas privada (parseUtc, calendarDaysUntil,
// refreshText). Se usan fechas relativas con margen para no depender de la zona
// horaria de la máquina que corre los tests.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RecPeriodNote from "./RecPeriodNote";

const daysFromNow = (n) => new Date(Date.now() + n * 86_400_000).toISOString();

describe("RecPeriodNote", () => {
  it("no renderiza nada si el período es desconocido", () => {
    const { container } = render(<RecPeriodNote period="yearly" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("muestra la etiqueta del período (semanal/mensual)", () => {
    render(<RecPeriodNote period="weekly" />);
    expect(screen.getByText(/Tu selección semanal/)).toBeInTheDocument();
    render(<RecPeriodNote period="monthly" />);
    expect(screen.getByText(/Tu selección mensual/)).toBeInTheDocument();
  });

  it("con next_refresh futuro dice cuántos días faltan", () => {
    render(<RecPeriodNote period="weekly" nextRefresh={daysFromNow(5)} />);
    expect(screen.getByText(/se renueva en \d+ días/)).toBeInTheDocument();
  });

  it("con next_refresh ya vencido dice que toca actualizar", () => {
    render(<RecPeriodNote period="weekly" nextRefresh={daysFromNow(-2)} />);
    expect(screen.getByText(/toca actualizarla/)).toBeInTheDocument();
  });

  it("acepta la fecha del backend SIN zona horaria (le añade la Z)", () => {
    // El backend serializa sin 'Z' ("2026-07-20T10:00:00"). No debe romper ni
    // interpretarse como hora local: parseUtc le añade la Z.
    const noZone = daysFromNow(5).replace("Z", "");
    render(<RecPeriodNote period="weekly" nextRefresh={noZone} />);
    expect(screen.getByText(/se renueva/)).toBeInTheDocument();
  });

  it("sin next_refresh solo muestra la etiqueta, sin la coletilla de renovación", () => {
    render(<RecPeriodNote period="weekly" />);
    expect(screen.getByText(/Tu selección semanal/)).toBeInTheDocument();
    expect(screen.queryByText(/se renueva/)).not.toBeInTheDocument();
  });
});
