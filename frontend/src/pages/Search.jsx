// src/pages/Search.jsx
// ----------------------------------------------------------------------------
// Pantalla de búsqueda (diseño Wavely). Busca en el catálogo de Spotify a
// través del gateway y muestra los resultados en una tabla. Estados:
//   - inicial: aún no se ha buscado
//   - resultados: hay coincidencias
//   - vacío: la búsqueda no devolvió nada
//
// Acciones por fila: el "like" (corazón) está cableado al backend; reproducir,
// añadir a playlist y chat IA quedan visuales por ahora (aún no hay esas
// páginas/servicios de UI).
// ----------------------------------------------------------------------------

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { usePlayer } from "../player/PlayerContext";
import {
  searchSongs,
  addLike,
  removeLike,
  listLikes,
  addDislike,
  removeDislike,
  listDislikes,
  getToken,
} from "../api";

// duration_ms (número) -> "m:ss"
function formatDuration(ms) {
  if (!ms && ms !== 0) return "—";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export default function Search() {
  const navigate = useNavigate();
  const player = usePlayer();

  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState(""); // término ya buscado
  const [results, setResults] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [likedIds, setLikedIds] = useState(() => new Set()); // spotify_track_id con like
  const [dislikedIds, setDislikedIds] = useState(() => new Set()); // con dislike

  // Guard de sesión: sin token no hay nada que buscar.
  useEffect(() => {
    if (!getToken()) {
      navigate("/");
      return;
    }
    // Precargamos likes y dislikes para pintar los botones en el estado correcto.
    listLikes()
      .then((likes) => setLikedIds(new Set(likes.map((l) => l.spotify_track_id))))
      .catch(() => {});
    listDislikes()
      .then((dis) => setDislikedIds(new Set(dis.map((d) => d.spotify_track_id))))
      .catch(() => {});
  }, [navigate]);

  const handleSearch = async (e) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    setLoading(true);
    setError(null);
    setHasSearched(true);
    setSubmittedQuery(q);
    try {
      const data = await searchSongs(q);
      setResults(data);
    } catch {
      setError("Ocurrió un error al buscar. Inténtalo de nuevo.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const resetSearch = () => {
    setQuery("");
    setSubmittedQuery("");
    setResults([]);
    setHasSearched(false);
    setError(null);
  };

  // Quita un id de un Set de estado (helper para la exclusión mutua like/dislike).
  const removeFrom = (setter, trackId) =>
    setter((prev) => {
      const next = new Set(prev);
      next.delete(trackId);
      return next;
    });

  const toggleLike = async (trackId) => {
    const wasLiked = likedIds.has(trackId);
    // Actualización optimista de la UI; revertimos si el backend falla.
    setLikedIds((prev) => {
      const next = new Set(prev);
      if (wasLiked) next.delete(trackId);
      else next.add(trackId);
      return next;
    });
    // Like y dislike son mutuamente excluyentes (el backend también lo aplica).
    if (!wasLiked) removeFrom(setDislikedIds, trackId);
    try {
      if (wasLiked) await removeLike(trackId);
      else await addLike(trackId);
    } catch {
      setLikedIds((prev) => {
        const next = new Set(prev);
        if (wasLiked) next.add(trackId);
        else next.delete(trackId);
        return next;
      });
    }
  };

  const toggleDislike = async (trackId) => {
    const wasDisliked = dislikedIds.has(trackId);
    setDislikedIds((prev) => {
      const next = new Set(prev);
      if (wasDisliked) next.delete(trackId);
      else next.add(trackId);
      return next;
    });
    if (!wasDisliked) removeFrom(setLikedIds, trackId);
    try {
      if (wasDisliked) await removeDislike(trackId);
      else await addDislike(trackId);
    } catch {
      setDislikedIds((prev) => {
        const next = new Set(prev);
        if (wasDisliked) next.add(trackId);
        else next.delete(trackId);
        return next;
      });
    }
  };

  return (
    <Layout>
      <h1 className="page-title">Búsqueda</h1>
      <p className="page-subtitle">
        Encuentra canciones, artistas y álbumes en el catálogo de Spotify
      </p>

      <form className="search-form" onSubmit={handleSearch}>
        <input
          className="input"
          type="text"
          placeholder="Canción, artista o álbum…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn" type="submit" disabled={loading}>
          <span aria-hidden="true">⌕</span> {loading ? "Buscando…" : "Buscar"}
        </button>
      </form>

      {/* Estado inicial: aún no se ha buscado */}
      {!hasSearched && !loading && (
        <div className="state">
          <span className="state__icon">⌕</span>
          <p className="state__hint">
            Busca cualquier canción, artista o álbum para empezar.
          </p>
        </div>
      )}

      {error && (
        <div className="state">
          <span className="state__icon">⚠</span>
          <p className="state__title">Algo salió mal</p>
          <p className="state__hint">{error}</p>
        </div>
      )}

      {/* Resultados */}
      {hasSearched && !loading && !error && results.length > 0 && (
        <>
          <p className="results-count">
            {results.length} resultado{results.length !== 1 ? "s" : ""} para “
            {submittedQuery}”
          </p>
          <table className="track-table">
            <thead>
              <tr>
                <th className="col-index">#</th>
                <th>Canción / Artista</th>
                <th>Álbum</th>
                <th>Duración</th>
                <th style={{ textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {results.map((track, i) => {
                const liked = likedIds.has(track.spotify_track_id);
                const disliked = dislikedIds.has(track.spotify_track_id);
                return (
                  <tr key={track.spotify_track_id}>
                    <td className="col-index">{i + 1}</td>
                    <td>
                      <div className="track-cell">
                        {track.cover_url ? (
                          <img
                            className="track-cover"
                            src={track.cover_url}
                            alt=""
                          />
                        ) : (
                          <span className="track-cover" />
                        )}
                        <div>
                          <div className="track-name">{track.name}</div>
                          <div className="track-artist">{track.artist}</div>
                        </div>
                      </div>
                    </td>
                    <td className="col-album">{track.album || "—"}</td>
                    <td className="col-duration">
                      {formatDuration(track.duration_ms)}
                    </td>
                    <td>
                      <div className="track-actions">
                        <button
                          className="icon-btn"
                          onClick={() => player.playTrack(track)}
                          title="Reproducir"
                          aria-label="Reproducir"
                        >
                          ▶
                        </button>
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
                          {disliked ? "👎" : "👎"}
                        </button>
                        <button
                          className="icon-btn"
                          disabled
                          title="Añadir a playlist (próximamente)"
                          aria-label="Añadir a playlist"
                        >
                          ≡
                        </button>
                        <button
                          className="icon-btn"
                          disabled
                          title="Preguntar a la IA (próximamente)"
                          aria-label="Chat IA"
                        >
                          💬
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}

      {/* Sin resultados */}
      {hasSearched && !loading && !error && results.length === 0 && (
        <div className="state">
          <span className="state__icon">♪</span>
          <p className="state__title">Sin resultados para “{submittedQuery}”</p>
          <p className="state__hint">
            Intenta con otro término. Puedes buscar por nombre de canción, artista
            o álbum.
          </p>
          <button className="btn-ghost btn" onClick={resetSearch}>
            Nueva búsqueda
          </button>
        </div>
      )}
    </Layout>
  );
}
