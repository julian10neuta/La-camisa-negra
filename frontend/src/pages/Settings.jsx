// src/pages/Settings.jsx
// ----------------------------------------------------------------------------
// Ajustes del usuario. Todo lo que se toca aquí se guarda y se aplica al
// instante (no hay botón de "Guardar"): el cambio se ve en esta misma pantalla,
// que es la mejor forma de decidir si el tamaño de letra o la paleta te sirven.
//
// Los ajustes viven en este navegador (localStorage) — ver settingsStore.js.
// ----------------------------------------------------------------------------

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { getToken } from "../api";
import { useSettings, useDisplayName } from "../settings/SettingsContext";

// ─── Piezas de formulario reutilizables dentro de esta pantalla ──────────────

// Una fila de opciones excluyentes. Es un radiogroup de verdad (no botones):
// así un lector de pantalla anuncia "opción 2 de 4" y se navega con flechas.
function Segmented({ label, hint, value, options, onChange }) {
  return (
    <div className="setting">
      <div className="setting__head">
        <span className="setting__label">{label}</span>
        {hint && <span className="setting__hint">{hint}</span>}
      </div>
      <div className="segmented" role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button
            key={o.value}
            role="radio"
            aria-checked={value === o.value}
            className={"segmented__opt" + (value === o.value ? " is-on" : "")}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Toggle({ label, hint, checked, onChange }) {
  return (
    <div className="setting">
      <div className="setting__head">
        <span className="setting__label">{label}</span>
        {hint && <span className="setting__hint">{hint}</span>}
      </div>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        className={"switch" + (checked ? " is-on" : "")}
        onClick={() => onChange(!checked)}
      >
        <span className="switch__knob" />
      </button>
    </div>
  );
}

// ─── Datos de las opciones ───────────────────────────────────────────────────

const FONT_SIZES = [
  { value: "sm", label: "Pequeña" },
  { value: "md", label: "Normal" },
  { value: "lg", label: "Grande" },
  { value: "xl", label: "Muy grande" },
];

const MOTION = [
  { value: "system", label: "Como mi sistema" },
  { value: "on", label: "Reducir" },
  { value: "off", label: "Permitir" },
];

// Cada paleta se describe por lo que le pasa a quien la necesita, no por el
// nombre clínico a secas: "deuteranopía" no le dice nada a casi nadie.
const PALETTES = [
  {
    value: "default",
    name: "Wavely",
    desc: "La paleta original, con acento magenta.",
  },
  {
    value: "deuteranopia",
    name: "Deuteranopía",
    desc: "Dificultad con el verde, la más común. Acento azul y ámbar.",
  },
  {
    value: "protanopia",
    name: "Protanopía",
    desc: "Dificultad con el rojo. Acento azul y ámbar.",
  },
  {
    value: "tritanopia",
    name: "Tritanopía",
    desc: "Dificultad con el azul. Acento rojo y verde azulado.",
  },
];

export default function Settings() {
  const navigate = useNavigate();
  const { settings, set, reset } = useSettings();
  const displayName = useDisplayName();

  // Guarda de sesión: mismo patrón que Home y Dashboard.
  useEffect(() => {
    if (!getToken()) navigate("/");
  }, [navigate]);

  return (
    <Layout>
      <h1 className="page-title">Ajustes</h1>
      <p className="page-subtitle">
        Se guardan en este navegador y se aplican al instante.
      </p>

      {/* ─── Perfil ─────────────────────────────────────────────────────── */}
      <section className="settings-section">
        <h2 className="settings-section__title">Perfil</h2>

        <div className="setting">
          <div className="setting__head">
            <label className="setting__label" htmlFor="nickname">
              Cómo quieres que te llamemos
            </label>
            <span className="setting__hint">
              Si lo dejas vacío usamos tu nombre de Spotify.
            </span>
          </div>
          <input
            id="nickname"
            className="input setting__input"
            type="text"
            maxLength={32}
            placeholder="Tu apodo"
            value={settings.nickname}
            onChange={(e) => set("nickname", e.target.value)}
          />
        </div>

        <p className="settings-preview">
          Te saludaremos así: <strong>Hola{displayName ? `, ${displayName}` : ""} 👋</strong>
        </p>
      </section>

      {/* ─── Accesibilidad ──────────────────────────────────────────────── */}
      <section className="settings-section">
        <h2 className="settings-section__title">Accesibilidad</h2>

        <Segmented
          label="Tamaño de letra"
          hint="Se multiplica por el tamaño que ya tengas en tu navegador."
          value={settings.fontSize}
          options={FONT_SIZES}
          onChange={(v) => set("fontSize", v)}
        />

        <div className="setting setting--block">
          <div className="setting__head">
            <span className="setting__label">Colores</span>
            <span className="setting__hint">
              El magenta de Wavely se ve gris con las deficiencias de rojo-verde.
              Estas paletas cambian los acentos por combinaciones que sí se
              distinguen.
            </span>
          </div>
          <div className="palette-grid" role="radiogroup" aria-label="Paleta de colores">
            {PALETTES.map((p) => (
              <button
                key={p.value}
                role="radio"
                aria-checked={settings.palette === p.value}
                className={
                  "palette-card" + (settings.palette === p.value ? " is-on" : "")
                }
                onClick={() => set("palette", p.value)}
              >
                {/* Las muestras se pintan con la propia paleta: el CSS lee el
                    atributo data-preview y aplica esas variables aquí dentro,
                    así se ve el color real antes de elegirlo. */}
                <span className="palette-card__swatches" data-preview={p.value} aria-hidden="true">
                  <span className="palette-card__dot palette-card__dot--1" />
                  <span className="palette-card__dot palette-card__dot--2" />
                </span>
                <span className="palette-card__name">{p.name}</span>
                <span className="palette-card__desc">{p.desc}</span>
              </button>
            ))}
          </div>
        </div>

        <Toggle
          label="Alto contraste"
          hint="Aclara los textos tenues y oscurece el fondo."
          checked={settings.contrast === "high"}
          onChange={(on) => set("contrast", on ? "high" : "normal")}
        />

        <Segmented
          label="Movimiento"
          hint="Apaga el fondo animado y las transiciones. Útil si el movimiento te marea."
          value={settings.reduceMotion}
          options={MOTION}
          onChange={(v) => set("reduceMotion", v)}
        />
      </section>

      <div className="settings-footer">
        <button className="btn-ghost" onClick={reset}>
          Restablecer todo
        </button>
      </div>
    </Layout>
  );
}
