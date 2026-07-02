// src/components/NowPlaying.jsx
// ----------------------------------------------------------------------------
// Vista de reproducción completa (overlay deslizante), según el mockup "Player":
// carátula grande, título/artista/álbum, barra de progreso, controles y acciones.
// Se abre desde la barra inferior y se cierra con "‹ Volver" (sin cambiar de URL).
//
// Vivo: play/pausa, buscar (seek), like. Inerte por ahora: anterior/siguiente
// (reproducimos una sola canción), shuffle, "Preguntar a la IA" y "Recomendaciones".
// ----------------------------------------------------------------------------

import { useEffect, useState } from "react";
import { usePlayer } from "../player/PlayerContext";
import { addLike, removeLike, listLikes } from "../api";

function fmt(ms) {
  if (!ms && ms !== 0) return "0:00";
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function NowPlaying() {
  const player = usePlayer();
  const { current, paused, position, duration, expanded, errorMsg, togglePlay, seek, setExpanded } =
    player;

  const [liked, setLiked] = useState(false);

  // Al abrir con una canción, consultamos si ya está en favoritos.
  useEffect(() => {
    if (!expanded || !current) return;
    let alive = true;
    listLikes()
      .then((likes) => {
        if (alive) setLiked(likes.some((l) => l.spotify_track_id === current.spotify_track_id));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [expanded, current]);

  if (!expanded || !current) return null;

  const toggleLike = async () => {
    const was = liked;
    setLiked(!was);
    try {
      if (was) await removeLike(current.spotify_track_id);
      else await addLike(current.spotify_track_id);
    } catch {
      setLiked(was); // revertir si falla
    }
  };

  return (
    <div className="nowplaying">
      <div className="nowplaying__top">
        <button className="btn-ghost btn nowplaying__back" onClick={() => setExpanded(false)}>
          ‹ Volver
        </button>
        <span className="playerbar__spotify">● Spotify</span>
      </div>

      <div className="nowplaying__body">
        {current.cover_url ? (
          <img className="nowplaying__cover" src={current.cover_url} alt="" />
        ) : (
          <div className="nowplaying__cover" />
        )}

        <h2 className="nowplaying__title">{current.name}</h2>
        <p className="nowplaying__artist">{current.artist}</p>
        {current.album && <p className="nowplaying__album">{current.album}</p>}

        {errorMsg && <p className="nowplaying__error">{errorMsg}</p>}

        <div className="nowplaying__progress">
          <span className="nowplaying__time">{fmt(position)}</span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            value={Math.min(position, duration || 0)}
            onChange={(e) => seek(Number(e.target.value))}
            className="nowplaying__seek"
            aria-label="Progreso"
          />
          <span className="nowplaying__time">{fmt(duration)}</span>
        </div>

        <div className="nowplaying__controls">
          <button className="icon-btn" disabled aria-label="Anterior">⏮</button>
          <button className="nowplaying__play" onClick={togglePlay} aria-label={paused ? "Reproducir" : "Pausar"}>
            {paused ? "▶" : "⏸"}
          </button>
          <button className="icon-btn" disabled aria-label="Siguiente">⏭</button>
        </div>

        <div className="nowplaying__actions">
          <button className="icon-btn" disabled title="Aleatorio (próximamente)" aria-label="Aleatorio">🔀</button>
          <button
            className={"icon-btn" + (liked ? " is-active" : "")}
            onClick={toggleLike}
            title={liked ? "Quitar de favoritos" : "Añadir a favoritos"}
            aria-label="Favorito"
          >
            {liked ? "♥" : "♡"}
          </button>
          <button className="btn-ghost btn nowplaying__ai" disabled title="Próximamente">
            💬 Preguntar a la IA
          </button>
        </div>

        <p className="nowplaying__queue">Siguiente de: + Recomendaciones</p>
      </div>
    </div>
  );
}
