// src/pages/Home.jsx
// ----------------------------------------------------------------------------
// Home: la pantalla a la que se llega tras el login.
//
// La primera versión eran unas viñetas que enlazaban a las demás pantallas. Se
// quitaron por redundantes: una tarjeta que dice "ve al Dashboard" es un clic de
// más para llegar a algo que cabe aquí mismo. Ahora el Home TRAE el contenido en
// vez de apuntar a él: lo que estabas escuchando, tus recomendaciones (con su
// período), y el resumen de tu semana. La navegación ya la da el Layout.
//
// Las tres secciones se piden EN PARALELO y cada una se pinta cuando llega. Es
// importante: /recommendations/list puede tardar ~17s si toca regenerar, y sería
// absurdo que el saludo y el historial esperaran por ello.
// ----------------------------------------------------------------------------

import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Layout from "../components/Layout";
import RecPeriodNote from "../components/RecPeriodNote";
import { usePlayer } from "../player/PlayerContext";
import { useSettings, useDisplayName } from "../settings/SettingsContext";
import { getToken, getRecommendations, getHistory, getStats } from "../api";

// Cuántas recomendaciones se ven en el Home. Se PIDEN todas las que el usuario
// tenga configuradas (para no generar una lista distinta a la del Dashboard, que
// obligaría a regenerar) y aquí solo se muestran las primeras.
const RECS_SHOWN = 5;
const HISTORY_SHOWN = 6;
const STATS_DAYS = 7;

function greeting() {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return "Buenos días";
  if (h >= 12 && h < 20) return "Buenas tardes";
  return "Buenas noches";
}

// 1284 -> "1.284"; 12900 -> "12,9 mil". Los números grandes en crudo se leen mal
// de un vistazo, y estas fichas son justo para leerlas de un vistazo.
function compact(n) {
  if (n == null) return "—";
  if (n < 1000) return String(n);
  if (n < 10000) return `${(n / 1000).toLocaleString("es", { maximumFractionDigits: 1 })} mil`;
  return `${Math.round(n / 1000).toLocaleString("es")} mil`;
}

// ─── Piezas ──────────────────────────────────────────────────────────────────

function TrackCard({ track, onPlay }) {
  return (
    <div className="home-track">
      <button className="home-track__art" onClick={onPlay} aria-label={`Reproducir ${track.name}`}>
        {track.cover_url ? (
          <img src={track.cover_url} alt="" loading="lazy" />
        ) : (
          <span className="home-track__placeholder" aria-hidden="true">♪</span>
        )}
        <span className="home-track__play" aria-hidden="true">▶</span>
      </button>
      <div className="home-track__name" title={track.name}>{track.name}</div>
      <div className="home-track__artist" title={track.artist}>{track.artist}</div>
    </div>
  );
}

// Ficha de estadística. Sin gráfico ni sparkline a propósito: son tres números
// sueltos, y un número suelto no necesita más que decirse claro.
function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
    </div>
  );
}

function Section({ title, note, action, children }) {
  return (
    <section className="home-section">
      <div className="home-section__head">
        <div>
          <h2 className="home-section__title">{title}</h2>
          {note}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

// ─── Pantalla ────────────────────────────────────────────────────────────────

export default function Home() {
  const navigate = useNavigate();
  const player = usePlayer();
  const name = useDisplayName();
  const { settings } = useSettings();
  const { period, recCount } = settings;

  const [query, setQuery] = useState("");
  const [recs, setRecs] = useState({ tracks: [], period: null, nextRefresh: null });
  const [recsState, setRecsState] = useState("loading"); // loading | ready | error
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);

  // Guarda de sesión: sin token, de vuelta al login (mismo patrón que Dashboard).
  useEffect(() => {
    if (!getToken()) navigate("/");
  }, [navigate]);

  // Historial y estadísticas: rápidos y no dependen de los ajustes.
  useEffect(() => {
    if (!getToken()) return;
    getHistory(HISTORY_SHOWN).then(setHistory).catch(() => setHistory([]));
    getStats(STATS_DAYS).then(setStats).catch(() => setStats(null));
  }, []);

  // Recomendaciones: dependen del período y del número elegidos en Ajustes, y
  // pueden tardar. Van en su propio efecto para no rehacer las otras dos.
  useEffect(() => {
    if (!getToken()) return;
    setRecsState("loading");
    getRecommendations({ period, limit: recCount })
      .then((d) => {
        setRecs({
          tracks: d.tracks || [],
          period: d.period,
          nextRefresh: d.next_refresh,
        });
        setRecsState("ready");
      })
      .catch(() => setRecsState("error"));
  }, [period, recCount]);

  const submitSearch = (e) => {
    e.preventDefault();
    const q = query.trim();
    if (q) navigate(`/search?q=${encodeURIComponent(q)}`);
  };

  return (
    <Layout>
      {/* ─── Hero: saludo + buscador ──────────────────────────────────────── */}
      <section className="home-hero">
        <div className="home-hero__top">
          <span className="home-hero__eyebrow">Inicio</span>
          <Link to="/settings" className="btn-ghost home-hero__settings">
            <span aria-hidden="true">⚙</span> Ajustes
          </Link>
        </div>
        <h1 className="home-hero__title">
          {greeting()}{name ? `, ${name}` : ""} 👋
        </h1>
        <p className="home-hero__subtitle">¿Qué quieres escuchar hoy?</p>

        <form className="home-hero__search" onSubmit={submitSearch} role="search">
          <input
            className="input"
            type="search"
            placeholder="Canción, artista o álbum…"
            aria-label="Buscar música"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="btn" type="submit">
            <span aria-hidden="true">⌕</span> Buscar
          </button>
        </form>
      </section>

      {/* ─── Sigue escuchando ─────────────────────────────────────────────── */}
      {/* Se oculta entero si no hay nada: un hueco vacío no aporta. */}
      {history.length > 0 && (
        <Section title="Sigue escuchando">
          <div className="home-row">
            {history.map((track, i) => (
              <TrackCard
                key={track.spotify_track_id}
                track={track}
                onPlay={() => player.playTrack(track, { queue: history, index: i })}
              />
            ))}
          </div>
        </Section>
      )}

      {/* ─── Recomendado para ti ──────────────────────────────────────────── */}
      <Section
        title="Recomendado para ti"
        note={<RecPeriodNote period={recs.period} nextRefresh={recs.nextRefresh} />}
        action={
          recs.tracks.length > RECS_SHOWN && (
            <Link to="/dashboard" className="home-section__more">
              Ver todas ({recs.tracks.length}) →
            </Link>
          )
        }
      >
        {recsState === "loading" && (
          <div className="state">
            <span className="state__icon">✦</span>
            <p className="state__hint">Buscando canciones para ti…</p>
          </div>
        )}

        {recsState === "error" && (
          <div className="state">
            <span className="state__icon">⚠</span>
            <p className="state__hint">No se pudieron cargar las recomendaciones.</p>
          </div>
        )}

        {recsState === "ready" && recs.tracks.length === 0 && (
          <div className="state">
            <span className="state__icon">✦</span>
            <p className="state__title">Aún no hay recomendaciones</p>
            <p className="state__hint">
              Reproduce, marca favoritos y descarta algunas canciones. Con esas
              señales el motor arma tus recomendaciones.
            </p>
          </div>
        )}

        {recsState === "ready" && recs.tracks.length > 0 && (
          <div className="home-row">
            {recs.tracks.slice(0, RECS_SHOWN).map((track, i) => (
              <TrackCard
                key={track.spotify_track_id}
                track={track}
                /* La cola es la lista COMPLETA, no solo las 5 visibles: así al
                   acabarse las de pantalla la música sigue. El índice coincide
                   porque el slice empieza en 0. */
                onPlay={() => player.playTrack(track, { queue: recs.tracks, index: i })}
              />
            ))}
          </div>
        )}
      </Section>

      {/* ─── Tu semana en Wavely ──────────────────────────────────────────── */}
      {stats && (
        <Section title="Tu semana en Wavely">
          <div className="stat-row">
            <Stat label="Reproducciones" value={compact(stats.plays)} />
            <Stat label="Minutos escuchados" value={compact(Math.round(stats.seconds_listened / 60))} />
            <Stat label="Artista más escuchado" value={stats.top_artist || "—"} />
          </div>
          {stats.plays === 0 && (
            <p className="home-section__hint">
              Todavía no has escuchado nada esta semana. Dale al play y esto se
              llena solo.
            </p>
          )}
        </Section>
      )}
    </Layout>
  );
}
