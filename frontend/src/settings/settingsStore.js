// src/settings/settingsStore.js
// ----------------------------------------------------------------------------
// Lectura, escritura y aplicación de las preferencias del usuario.
//
// Los ajustes viven en localStorage (no en el backend): son preferencias de
// presentación de este navegador y así la app no depende de la red para
// pintarse bien. La contrapartida es que no viajan a otro equipo.
//
// La aplicación es por atributos en <html> (data-font-size, data-palette,
// data-contrast, data-motion). El CSS reacciona a esos atributos redefiniendo
// las variables de :root, así que ninguna pantalla necesita saber que los
// ajustes existen.
//
// Este módulo es JS puro a propósito (sin React): `applySettings` se llama en
// main.jsx ANTES del primer render para que no se vea un parpadeo con el tema
// equivocado.
// ----------------------------------------------------------------------------

const STORAGE_KEY = "wavely:settings";

// `reduceMotion: "system"` = obedecer la preferencia del sistema operativo
// (prefers-reduced-motion). Es el default correcto: si alguien ya le dijo a su
// sistema que no quiere animaciones, no tiene por qué repetírnoslo a nosotros.
export const DEFAULTS = {
  nickname: "",           // "" = usar el nombre que vino de Spotify
  fontSize: "md",         // sm | md | lg | xl
  palette: "default",     // default | protanopia | deuteranopia | tritanopia
  contrast: "normal",     // normal | high
  reduceMotion: "system", // system | on | off
  period: "weekly",       // weekly | monthly  (recomendaciones)
  recCount: 15,           // cuántas recomendaciones pedir
  autoplay: true,         // seguir sonando al agotarse la cola
};

// Valores admitidos. Sirve para saneamiento: si alguien edita el localStorage a
// mano (o llega un ajuste de una versión vieja), caemos al default en vez de
// escribir basura en el DOM.
const ALLOWED = {
  fontSize: ["sm", "md", "lg", "xl"],
  palette: ["default", "protanopia", "deuteranopia", "tritanopia"],
  contrast: ["normal", "high"],
  reduceMotion: ["system", "on", "off"],
  period: ["weekly", "monthly"],
  recCount: [10, 15, 25],
};

function sanitize(raw) {
  const out = { ...DEFAULTS };
  if (!raw || typeof raw !== "object") return out;

  for (const [key, values] of Object.entries(ALLOWED)) {
    if (values.includes(raw[key])) out[key] = raw[key];
  }
  if (typeof raw.nickname === "string") out.nickname = raw.nickname.slice(0, 32);
  if (typeof raw.autoplay === "boolean") out.autoplay = raw.autoplay;

  return out;
}

export function loadSettings() {
  try {
    return sanitize(JSON.parse(localStorage.getItem(STORAGE_KEY)));
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveSettings(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Modo incógnito o almacenamiento lleno: la app sigue funcionando con los
    // ajustes en memoria, solo no se recuerdan al recargar.
  }
}

// Escribe los ajustes visuales en <html>. El CSS hace el resto.
export function applySettings(settings) {
  const el = document.documentElement;
  el.dataset.fontSize = settings.fontSize;
  el.dataset.palette = settings.palette;
  el.dataset.contrast = settings.contrast;

  // "system" = no ponemos atributo y deja mandar a la media query
  // prefers-reduced-motion del CSS.
  if (settings.reduceMotion === "system") {
    delete el.dataset.motion;
  } else {
    el.dataset.motion = settings.reduceMotion === "on" ? "reduce" : "full";
  }
}

// ¿Hay que apagar las animaciones ahora mismo? Lo usa el fondo aurora para no
// montar siquiera la animación (el CSS ya la apaga, pero así tampoco gastamos
// pintado). Combina nuestro ajuste con la preferencia del sistema.
export function motionReduced(settings) {
  if (settings.reduceMotion === "on") return true;
  if (settings.reduceMotion === "off") return false;
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}
