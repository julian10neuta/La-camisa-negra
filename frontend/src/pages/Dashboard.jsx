// src/pages/Dashboard.jsx
// ----------------------------------------------------------------------------
// Dashboard: por ahora muestra la sección "Recomendado para ti" (el motor de
// recomendación). El dashboard completo de estadísticas (top canciones/artistas/
// álbumes, ventanas 24h/7d) del mockup es otra entrega.
//
// Cada tarjeta permite reproducir, dar like y dar dislike (mismas señales que
// alimentan el propio motor).
// ----------------------------------------------------------------------------

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import RecPeriodNote from "../components/RecPeriodNote";
import { usePlayer } from "../player/PlayerContext";
import { useSettings } from "../settings/SettingsContext";
import {
  getRecommendations,
  refreshRecommendations,
  addLike,
  removeLike,
  addDislike,
  removeDislike,
  listLikes,
  listDislikes,
  getToken,
} from "../api";

function Dashboard() {
  const navigate = useNavigate();
  const player = usePlayer();
  const { settings } = useSettings();
  const { period, recCount } = settings;

  const [tracks, setTracks] = useState([]);
  const [playlistUrl, setPlaylistUrl] = useState(null);
  const [meta, setMeta] = useState({ period: null, nextRefresh: null });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [likedIds, setLikedIds] = useState(() => new Set());
  const [dislikedIds, setDislikedIds] = useState(() => new Set());

  const applyResult = (data) => {
    setTracks(data.tracks || []);
    setPlaylistUrl(data.playlist_url || null);
    // El período que se muestra es el que respondió el backend, no el del
    // ajuste: si alguna vez difirieran, lo cierto es lo que se está pintando.
    setMeta({ period: data.period, nextRefresh: data.next_refresh });
  };

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

  // Las recomendaciones sí dependen de los ajustes: si el usuario cambia el
  // período o el número, hay que volver a pedirlas.
  useEffect(() => {
    if (!getToken()) return;
    setLoading(true);
    setError(null);
    getRecommendations({ period, limit: recCount })
      .then(applyResult)
      .catch(() => setError("No se pudieron cargar las recomendaciones."))
      .finally(() => setLoading(false));
  }, [period, recCount]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      applyResult(await refreshRecommendations({ period, limit: recCount }));
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

  return (
    <Layout>
      <div className="dash-header">
        <div>
          <h1 className="page-title">Recomendado para ti</h1>
          <p className="page-subtitle">
            Canciones nuevas según tu escucha, tus likes y tus dislikes
          </p>
          <RecPeriodNote period={meta.period} nextRefresh={meta.nextRefresh} />
        </div>
        <div className="dash-header__actions">
          {playlistUrl && (
            <a className="btn-ghost btn" href={playlistUrl} target="_blank" rel="noreferrer">
              Abrir en Spotify
            </a>
          )}
          <button className="btn" onClick={handleRefresh} disabled={refreshing || loading}>
            {refreshing ? "Regenerando…" : "↻ Regenerar"}
          </button>
        </div>
      </div>

      {loading && (
        <div className="state">
          <span className="state__icon">✦</span>
          <p className="state__hint">Generando recomendaciones…</p>
        </div>
      )}

      {error && !loading && (
        <div className="state">
          <span className="state__icon">⚠</span>
          <p className="state__hint">{error}</p>
        </div>
      )}

      {!loading && !error && tracks.length === 0 && (
        <div className="state">
          <span className="state__icon">✦</span>
          <p className="state__title">Aún no hay recomendaciones</p>
          <p className="state__hint">
            Reproduce, marca favoritos y descarta algunas canciones en la Búsqueda.
            Con esas señales el motor arma tus recomendaciones.
          </p>
        </div>
      )}

      {!loading && tracks.length > 0 && (
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
    </Layout>
  );
}

export default Dashboard;
