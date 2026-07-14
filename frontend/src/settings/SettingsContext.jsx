// src/settings/SettingsContext.jsx
// ----------------------------------------------------------------------------
// Estado global de las preferencias del usuario, con el mismo patrón de React
// Context que ya usa el reproductor (player/PlayerContext.jsx).
//
// Cualquier pantalla lee los ajustes con `useSettings()` y los cambia con
// `set(clave, valor)`. Cada cambio se guarda en localStorage y se aplica al DOM
// en el acto, así que no hace falta un botón de "Guardar".
// ----------------------------------------------------------------------------

import { createContext, useContext, useCallback, useEffect, useState } from "react";
import { applySettings, loadSettings, saveSettings, DEFAULTS } from "./settingsStore";

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(loadSettings);

  // Persistir + aplicar en cada cambio. main.jsx ya aplicó los ajustes antes
  // del primer render; esto cubre los cambios posteriores.
  useEffect(() => {
    saveSettings(settings);
    applySettings(settings);
  }, [settings]);

  const set = useCallback((key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }, []);

  const reset = useCallback(() => setSettings({ ...DEFAULTS }), []);

  return (
    <SettingsContext.Provider value={{ settings, set, reset }}>
      {children}
    </SettingsContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings debe usarse dentro de <SettingsProvider>");
  return ctx;
}

// El nombre con el que la app se dirige al usuario: el apodo que él eligió y,
// si no puso ninguno, el nombre que vino de Spotify (lo guardó el Callback).
// eslint-disable-next-line react-refresh/only-export-components
export function useDisplayName() {
  const { settings } = useSettings();
  if (settings.nickname.trim()) return settings.nickname.trim();
  try {
    return JSON.parse(localStorage.getItem("user"))?.name || null;
  } catch {
    return null;
  }
}
