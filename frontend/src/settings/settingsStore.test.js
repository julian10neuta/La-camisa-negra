// Tests de settingsStore.js — el saneamiento y la aplicación de las preferencias.
// Es JS puro sobre localStorage y <html>; jsdom provee ambos.
import { beforeEach, describe, it, expect, vi } from "vitest";
import {
  DEFAULTS,
  loadSettings,
  saveSettings,
  applySettings,
  motionReduced,
} from "./settingsStore";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-motion");
});

describe("loadSettings / sanitize", () => {
  it("sin nada guardado devuelve los defaults", () => {
    expect(loadSettings()).toEqual(DEFAULTS);
  });

  it("un valor inválido cae al default, uno válido se conserva", () => {
    localStorage.setItem("wavely:settings", JSON.stringify({
      fontSize: "gigante",   // inválido → default "md"
      palette: "protanopia", // válido → se conserva
      recCount: 999,         // no está en [10,15,25] → default 15
    }));
    const s = loadSettings();
    expect(s.fontSize).toBe("md");
    expect(s.palette).toBe("protanopia");
    expect(s.recCount).toBe(15);
  });

  it("recorta el apodo a 32 caracteres y respeta el booleano autoplay", () => {
    localStorage.setItem("wavely:settings", JSON.stringify({
      nickname: "x".repeat(50), autoplay: false,
    }));
    const s = loadSettings();
    expect(s.nickname).toHaveLength(32);
    expect(s.autoplay).toBe(false);
  });

  it("un JSON corrupto no revienta: devuelve defaults", () => {
    localStorage.setItem("wavely:settings", "{roto");
    expect(loadSettings()).toEqual(DEFAULTS);
  });

  it("autoplay no booleano se ignora (queda el default true)", () => {
    localStorage.setItem("wavely:settings", JSON.stringify({ autoplay: "sí" }));
    expect(loadSettings().autoplay).toBe(true);
  });
});

describe("saveSettings", () => {
  it("hace roundtrip con loadSettings", () => {
    saveSettings({ ...DEFAULTS, palette: "tritanopia", recCount: 25 });
    const s = loadSettings();
    expect(s.palette).toBe("tritanopia");
    expect(s.recCount).toBe(25);
  });
});

describe("applySettings", () => {
  it("escribe los atributos data-* en <html>", () => {
    applySettings({ ...DEFAULTS, fontSize: "lg", palette: "deuteranopia", contrast: "high" });
    const el = document.documentElement;
    expect(el.dataset.fontSize).toBe("lg");
    expect(el.dataset.palette).toBe("deuteranopia");
    expect(el.dataset.contrast).toBe("high");
  });

  it("reduceMotion 'system' NO pone data-motion (deja mandar al CSS)", () => {
    applySettings({ ...DEFAULTS, reduceMotion: "system" });
    expect(document.documentElement.dataset.motion).toBeUndefined();
  });

  it("reduceMotion 'on' → data-motion=reduce; 'off' → full", () => {
    applySettings({ ...DEFAULTS, reduceMotion: "on" });
    expect(document.documentElement.dataset.motion).toBe("reduce");
    applySettings({ ...DEFAULTS, reduceMotion: "off" });
    expect(document.documentElement.dataset.motion).toBe("full");
  });
});

describe("motionReduced", () => {
  it("'on' siempre true, 'off' siempre false (sin mirar el sistema)", () => {
    expect(motionReduced({ reduceMotion: "on" })).toBe(true);
    expect(motionReduced({ reduceMotion: "off" })).toBe(false);
  });

  it("'system' obedece la media query del sistema", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    expect(motionReduced({ reduceMotion: "system" })).toBe(true);
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
    expect(motionReduced({ reduceMotion: "system" })).toBe(false);
    vi.unstubAllGlobals();
  });
});
