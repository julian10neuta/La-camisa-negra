// src/pages/Dashboard.jsx
// ----------------------------------------------------------------------------
// Dashboard: "Tu actividad musical". Lo que pide la tarjeta CRC del diseño — los
// cinco más escuchados en canciones, artistas y álbumes para una ventana de
// tiempo (24h / 7 días), más las recomendaciones.
//
// UNA sola llamada, a /dashboard, que el dashboard_service compone por dentro
// (ver backend/dashboard_service/services/composer.py). Antes esta pantalla solo
// pedía las recomendaciones; los tres rankings habrían sido tres viajes más.
//
// Las dos "ventanas" que conviven aquí, que es lo que más confunde:
//   - `days` (24h/7d) manda sobre las ESTADÍSTICAS. Es el selector de arriba.
//   - `period` (semanal/mensual) manda sobre las RECOMENDACIONES, y sale de
//     Ajustes. NO depende del selector: mirar tus stats de hoy no debería
//     cambiar qué recomendaciones tienes.
// ----------------------------------------------------------------------------

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import RecPeriodNote from "../components/RecPeriodNote";
import { usePlayer } from "../player/PlayerContext";
import { useSettings } from "../settings/SettingsContext";
import {
  getDashboard,
  refreshRecommendations,
  addLike,
  removeLike,
  addDislike,
  removeDislike,
  listLikes,
  listDislikes,
  getToken,
} from "../api";

// Las dos ventanas que pide el diseño. 24h = 1 día.
const WINDOWS = [
  { days: 1, label: "Últimas 24 horas" },
  { days: 7, label: "Últimos 7 días" },
];
const TOP_N = 5;

// ─── Piezas ──────────────────────────────────────────────────────────────────

function Cover({ url }) {
  return url ? (
    <img className="top-cover" src={url} alt="" loading="lazy" />
  ) : (
    <span className="top-cover top-cover--empty" aria-hidden="true">♪</span>
  );
}

// Una fila de ranking: puesto, carátula, texto y nº de escuchas. Si se le pasa
// onPlay se vuelve un <button> de verdad (enfocable, activable con Enter); si no,
// es un div, porque un botón que no hace nada es una mentira para quien navega
// con teclado o lector de pantalla.
function TopRow({ rank, cover, title, subtitle, plays, onPlay }) {
  const Tag = onPlay ? "button" : "div";
  return (
    <Tag
      className={"top-row" + (onPlay ? " is-playable" : "")}
      onClick={onPlay}
      {...(onPlay ? { "aria-label": `Reproducir ${title}` } : {})}
    >
      <span className="top-row__rank">{rank}</span>
      <Cover url={cover} />
      <span className="top-row__text">
        <span className="top-row__title" title={title}>{title}</span>
        {subtitle && <span className="top-row__sub" title={subtitle}>{subtitle}</span>}
      </span>
      <span className="top-row__plays">
        {plays} {plays === 1 ? "escucha" : "escuchas"}
      </span>
    </Tag>
  );
}

// Un hueco sin explicación deja al usuario pensando que la app falló.
function Empty({ children }) {
  return <p className="dash-empty">{children}</p>;
}

// ─── Pantalla ────────────────────────────────────────────────────────────────

function Dashboard() {
  const navigate = useNavigate();
  const player = usePlayer();
  const { settings } = useSettings();
  const { period, recCount } = settings;

  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [likedIds, setLikedIds] = useState(() => new Set());
  const [dislikedIds, setDislikedIds] = useState(() => new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getDashboard({ days, top: TOP_N, period, limit: recCount }));
    } catch {
      setError("No se pudo cargar tu actividad.");
    } finally {
      setLoading(false);
    }
  }, [days, period, recCount]);

  // Likes y dislikes: solo dependen del usuario, se piden una vez.
  useEffect(() => {
    if (!getToken()) {
      navigate("/");
      return;
    }
    listLikes()
      .then((l) => setLikedIds(new Set(l.map((x) => x.spotify_track_id))))
      .catch(() => {});
    listDislikes()
      .then((d) => setDislikedIds(new Set(d.map((x) => x.spotify_track_id))))
      .catch(() => {});
  }, [navigate]);

  // Se recarga al cambiar la ventana o los ajustes: es lo que pide el CRC
  // ("recalcular todo al cambiar la ventana").
  useEffect(() => {
    if (getToken()) load();
  }, [load]);

  // Regenerar va directo al recommendation_service: el dashboard_service solo lee
  // y compone, no escribe. Después se recarga para traer la lista nueva.
  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await refreshRecommendations({ period, limit: recCount });
      await load();
    } catch {
      setError("No se pudieron regenerar las recomendaciones.");
    } finally {
      setRefreshing(false);
    }
  };

  const removeFrom = (setter, id) =>
    setter((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });

  // toggle genérico para like/dislike (evita duplicar la lógica optimista).
  const makeToggle = (has, setter, otherSetter, add, remove) => async (id) => {
    const was = has(id);
    setter((prev) => {
      const next = new Set(prev);
      if (was) next.delete(id);
      else next.add(id);
      return next;
    });
    if (!was) removeFrom(otherSetter, id); // exclusión mutua like/dislike
    try {
      if (was) await remove(id);
      else await add(id);
    } catch {
      setter((prev) => {
        const next = new Set(prev);
        if (was) next.add(id);
        else next.delete(id);
        return next;
      });
    }
  };

  const toggleLike = makeToggle(
    (id) => likedIds.has(id), setLikedIds, setDislikedIds, addLike, removeLike
  );
  const toggleDislike = makeToggle(
    (id) => dislikedIds.has(id), setDislikedIds, setLikedIds, addDislike, removeDislike
  );

  const top = data?.top || { songs: [], artists: [], albums: [] };
  const recs = data?.recommendations;
  const tracks = recs?.tracks || [];
  const failed = data?.failed || [];
  const ventana = WINDOWS.find((w) => w.days === days)?.label.toLowerCase();

  return (
    <Layout>
      <div className="dash-header">
        <div>
          <h1 className="page-title">Tu actividad musical</h1>
          <p className="page-subtitle">
            Estadísticas y recomendaciones personalizadas basadas en tu escucha
          </p>
        </div>
        {/* Mismo control que los Ajustes: un radiogroup de verdad, así un lector
            de pantalla anuncia "opción 2 de 2" en vez de dos botones sueltos. */}
        <div className="segmented" role="radiogroup" aria-label="Ventana de tiempo">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              role="radio"
              aria-checked={days === w.days}
              className={"segmented__opt" + (days === w.days ? " is-on" : "")}
              onClick={() => setDays(w.days)}
              disabled={loading}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="state">
          <span className="state__icon">⚠</span>
          <p className="state__hint">{error}</p>
        </div>
      )}

      {loading && !data && (
        <div className="state">
          <span className="state__icon">✦</span>
          <p className="state__hint">Cargando tu actividad…</p>
        </div>
      )}

      {data && (
        <>
          {data.stats && (
            <div className="stat-row dash-stats">
              <div className="stat">
                <span className="stat__label">Reproducciones</span>
                <span className="stat__value">{data.stats.plays}</span>
              </div>
              <div className="stat">
                <span className="stat__label">Minutos escuchados</span>
                <span className="stat__value">
                  {Math.round(data.stats.seconds_listened / 60)}
                </span>
              </div>
              <div className="stat">
                <span className="stat__label">Canciones distintas</span>
                <span className="stat__value">{data.stats.distinct_songs}</span>
              </div>
            </div>
          )}

          {/* Un servicio caído se dice, no se disimula con ceros: un cero
              inventado miente, un "no se pudo cargar" no. */}
          {failed.length > 0 && (
            <div className="dash-stale">
              <span>
                No se pudieron cargar algunas secciones ({failed.join(", ")}). El
                resto de la pantalla sí está.
              </span>
              <button className="btn-ghost btn" onClick={load} disabled={loading}>
                Reintentar
              </button>
            </div>
          )}

          <section className="dash-section">
            <h2 className="dash-section__title">
              <span aria-hidden="true">♪</span> Canciones más escuchadas
            </h2>
            {top.songs.length === 0 ? (
              <Empty>No has escuchado nada en las {ventana}.</Empty>
            ) : (
              <div className="top-list">
                {top.songs.map((s, i) => (
                  <TopRow
                    key={s.spotify_track_id}
                    rank={i + 1}
                    cover={s.cover_url}
                    title={s.name}
                    subtitle={s.artist}
                    plays={s.plays}
                    onPlay={() => player.playTrack(s, { queue: top.songs, index: i })}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="dash-section">
            <h2 className="dash-section__title">
              <span aria-hidden="true">🎤</span> Artistas más escuchados
            </h2>
            {top.artists.length === 0 ? (
              <Empty>Aún no hay artistas en esta ventana.</Empty>
            ) : (
              <div className="top-list">
                {/* Sin foto ni género, y no por falta de ganas: Spotify solo da la
                    foto desde /artists (y guardamos el nombre del artista, no su
                    id) y devuelve los géneros VACÍOS para esta app — la misma
                    restricción que obligó al motor a usar Deezer. Se usa la
                    carátula de una de sus canciones. */}
                {top.artists.map((a, i) => (
                  <TopRow
                    key={a.artist}
                    rank={i + 1}
                    cover={a.cover_url}
                    title={a.artist}
                    plays={a.plays}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="dash-section">
            <h2 className="dash-section__title">
              <span aria-hidden="true">💿</span> Álbumes más escuchados
            </h2>
            {top.albums.length === 0 ? (
              <Empty>Aún no hay álbumes en esta ventana.</Empty>
            ) : (
              <div className="top-list">
                {top.albums.map((a, i) => (
                  <TopRow
                    key={`${a.album}—${a.artist}`}
                    rank={i + 1}
                    cover={a.cover_url}
                    title={a.album}
                    subtitle={a.artist}
                    plays={a.plays}
                  />
                ))}
              </div>
            )}
          </section>

          {/* ─── Recomendaciones ─────────────────────────────────────────── */}
          <section className="dash-section">
            <div className="dash-section__head">
              <div>
                <h2 className="dash-section__title">
                  <span aria-hidden="true">✦</span> Recomendado para ti
                </h2>
                <RecPeriodNote period={recs?.period} nextRefresh={recs?.next_refresh} />
              </div>
              <div className="dash-header__actions">
                {recs?.playlist_url && (
                  <a
                    className="btn-ghost btn"
                    href={recs.playlist_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Abrir en Spotify
                  </a>
                )}
                {tracks.length > 0 && (
                  <button className="btn" onClick={handleRefresh} disabled={refreshing}>
                    {refreshing ? "Regenerando…" : "↻ Regenerar"}
                  </button>
                )}
              </div>
            </div>

            {/* Caducadas: se enseñan las últimas y se ofrece actualizar. Leer no
                regenera — son 30-50 llamadas a Spotify y ya costó dos baneos. */}
            {recs?.stale && tracks.length > 0 && (
              <div className="dash-stale">
                <span>
                  <strong>Tus recomendaciones caducaron.</strong> Estas son las
                  últimas que generamos.
                </span>
                <button className="btn" onClick={handleRefresh} disabled={refreshing}>
                  {refreshing ? "Actualizando…" : "↻ Actualizar ahora"}
                </button>
              </div>
            )}

            {tracks.length === 0 && (
              <div className="state">
                <span className="state__icon">✦</span>
                <p className="state__title">Aún no tienes recomendaciones</p>
                <p className="state__hint">
                  Cuantas más canciones reproduzcas, marques como favoritas o
                  descartes, mejores serán. Genéralas cuando quieras — tarda unos
                  segundos.
                </p>
                <button
                  className="btn"
                  onClick={handleRefresh}
                  disabled={refreshing}
                  style={{ marginTop: 18 }}
                >
                  {refreshing ? "Generando…" : "✦ Generar mis recomendaciones"}
                </button>
              </div>
            )}

            {tracks.length > 0 && (
              <div className="rec-grid">
                {tracks.map((track, i) => {
                  const liked = likedIds.has(track.spotify_track_id);
                  const disliked = dislikedIds.has(track.spotify_track_id);
                  return (
                    <div className="rec-card" key={track.spotify_track_id}>
                      <div
                        className="rec-card__art"
                        onClick={() => player.playTrack(track, { queue: tracks, index: i })}
                      >
                        {track.cover_url ? (
                          <img src={track.cover_url} alt="" />
                        ) : (
                          <span className="rec-card__placeholder">♪</span>
                        )}
                        <span className="rec-card__play">▶</span>
                      </div>
                      <div className="rec-card__name">{track.name}</div>
                      <div className="rec-card__artist">{track.artist}</div>
                      <div className="rec-card__actions">
                        <button
                          className={"icon-btn" + (liked ? " is-active" : "")}
                          onClick={() => toggleLike(track.spotify_track_id)}
                          title={liked ? "Quitar de favoritos" : "Añadir a favoritos"}
                          aria-label="Favorito"
                        >
                          {liked ? "♥" : "♡"}
                        </button>
                        <button
                          className={"icon-btn" + (disliked ? " is-dislike" : "")}
                          onClick={() => toggleDislike(track.spotify_track_id)}
                          title={disliked ? "Quitar dislike" : "No me gusta"}
                          aria-label="No me gusta"
                        >
                          👎
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </>
      )}
    </Layout>
  );
}

export default Dashboard;
