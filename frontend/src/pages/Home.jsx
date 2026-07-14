// src/pages/Home.jsx
// ----------------------------------------------------------------------------
// Home: la pantalla de inicio a la que se llega apenas se entra a la app (tras
// el login). Por ahora es genérica — una bienvenida + accesos rápidos a las
// secciones existentes — a la espera de definir su contenido definitivo con el
// diseño Wavely. Usa el Layout compartido, así hereda la barra de navegación
// (con el botón de cerrar sesión) y el reproductor.
// ----------------------------------------------------------------------------

import { useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import Layout from "../components/Layout";
import { getToken } from "../api";

// El nombre del usuario lo guardó el Callback en localStorage tras el login.
function userName() {
  try {
    return JSON.parse(localStorage.getItem("user"))?.name || null;
  } catch {
    return null;
  }
}

// Accesos rápidos. `ready:false` = sección aún sin página (se muestra inerte).
const SHORTCUTS = [
  {
    to: "/dashboard",
    icon: "▦",
    title: "Recomendado para ti",
    desc: "Descubre canciones nuevas según lo que escuchas, tus likes y dislikes.",
    ready: true,
  },
  {
    to: "/search",
    icon: "⌕",
    title: "Buscar música",
    desc: "Encuentra canciones y artistas del catálogo y reprodúcelos al instante.",
    ready: true,
  },
  {
    to: null,
    icon: "≡",
    title: "Tus playlists",
    desc: "Organiza tu música en listas propias.",
    ready: false,
  },
  {
    to: null,
    icon: "💬",
    title: "Asistente IA",
    desc: "Pregunta en lenguaje natural sobre canciones y artistas.",
    ready: false,
  },
];

export default function Home() {
  const navigate = useNavigate();
  const name = userName();

  // Guarda de sesión: sin token, de vuelta al login (mismo patrón que Dashboard).
  useEffect(() => {
    if (!getToken()) navigate("/");
  }, [navigate]);

  return (
    <Layout>
      <section className="home-hero">
        <span className="home-hero__eyebrow">Inicio</span>
        <h1 className="home-hero__title">Hola{name ? `, ${name}` : ""} 👋</h1>
        <p className="home-hero__subtitle">
          Bienvenido a Wavely. Tu música, tus recomendaciones y tu asistente, en
          un solo lugar.
        </p>
      </section>

      <h2 className="home-section-title">Explorar</h2>
      <div className="home-grid">
        {SHORTCUTS.map((s) => {
          const inner = (
            <>
              <span className="home-card__icon" aria-hidden="true">
                {s.icon}
              </span>
              <span className="home-card__title">{s.title}</span>
              <span className="home-card__desc">{s.desc}</span>
              {!s.ready && <span className="home-card__badge">Próximamente</span>}
            </>
          );
          return s.ready ? (
            <Link key={s.title} to={s.to} className="home-card">
              {inner}
            </Link>
          ) : (
            <div key={s.title} className="home-card is-disabled" title="Próximamente">
              {inner}
            </div>
          );
        })}
      </div>
    </Layout>
  );
}
