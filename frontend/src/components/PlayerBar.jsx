// src/components/PlayerBar.jsx
// ----------------------------------------------------------------------------
// Barra inferior de reproducción, presente en todas las pantallas internas.
// Lee el estado global del reproductor. Si hay algo sonando, muestra la canción
// y controles vivos; al pulsarla (flecha ↑ o la info de la pista) abre la vista
// de reproducción (overlay). Si no hay nada, muestra el estado vacío.
//
// Siguiente/anterior quedan inertes porque reproducimos una sola canción (sin cola).
// ----------------------------------------------------------------------------

import { usePlayer } from "../player/PlayerContext";

function fmt(ms) {
  if (!ms && ms !== 0) return "0:00";
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function PlayerBar() {
  const player = usePlayer();
  const { current, paused, position, duration, togglePlay, next, prev, setExpanded } = player;

  // Estado vacío (nada en reproducción)
  if (!current) {
    return (
      <footer className="playerbar">
        <span className="playerbar__status">Ninguna canción en reproducción</span>
        <div className="playerbar__controls">
          <button className="icon-btn" disabled aria-label="Anterior">⏮</button>
          <button className="playerbar__play" disabled aria-label="Reproducir">▶</button>
          <button className="icon-btn" disabled aria-label="Siguiente">⏭</button>
          <button className="icon-btn" disabled aria-label="Volumen">🔊</button>
          <span className="playerbar__spotify">● Spotify</span>
        </div>
      </footer>
    );
  }

  return (
    <footer className="playerbar">
      <button
        className="playerbar__now"
        onClick={() => setExpanded(true)}
        title="Abrir vista de reproducción"
      >
        <span className="playerbar__chevron" aria-hidden="true">⌃</span>
        {current.cover_url ? (
          <img className="playerbar__cover" src={current.cover_url} alt="" />
        ) : (
          <span className="playerbar__cover" />
        )}
        <span className="playerbar__meta">
          <span className="playerbar__track">{current.name}</span>
          <span className="playerbar__artist">{current.artist}</span>
        </span>
      </button>

      <div className="playerbar__controls">
        <button className="icon-btn" onClick={prev} aria-label="Anterior">⏮</button>
        <button className="playerbar__play" onClick={togglePlay} aria-label={paused ? "Reproducir" : "Pausar"}>
          {paused ? "▶" : "⏸"}
        </button>
        <button className="icon-btn" onClick={next} aria-label="Siguiente">⏭</button>
        <span className="playerbar__time">
          {fmt(position)} / {fmt(duration)}
        </span>
        <button className="icon-btn" disabled aria-label="Volumen">🔊</button>
        <span className="playerbar__spotify">● Spotify</span>
      </div>
    </footer>
  );
}
