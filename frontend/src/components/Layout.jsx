// src/components/Layout.jsx
// ----------------------------------------------------------------------------
// "Chrome" compartido de las pantallas internas: barra de navegación superior
// (Dashboard / Búsqueda / Playlists / Chat IA) y barra de reproductor inferior.
// El contenido de cada página se pasa como children y se pinta en el centro.
//
// Playlists y Chat IA todavía no tienen página, así que se muestran pero
// inertes (sin enlace) hasta que existan.
// ----------------------------------------------------------------------------

import { NavLink } from "react-router-dom";
import PlayerBar from "./PlayerBar";

// NavLink pinta la clase "is-active" automáticamente cuando la ruta coincide.
function Item({ to, icon, label, disabled }) {
  if (disabled) {
    return (
      <span className="navlink is-disabled" title="Próximamente">
        <span aria-hidden="true">{icon}</span>
        {label}
      </span>
    );
  }
  return (
    <NavLink
      to={to}
      className={({ isActive }) => "navlink" + (isActive ? " is-active" : "")}
    >
      <span aria-hidden="true">{icon}</span>
      {label}
    </NavLink>
  );
}

function Brand() {
  return (
    <span className="brand">
      <span className="brand__badge">♪</span>
      Wavely
    </span>
  );
}

export default function Layout({ children }) {
  return (
    <div className="app-shell">
      <header className="topnav">
        <Brand />
        <nav className="topnav__links">
          <Item to="/dashboard" icon="▦" label="Dashboard" />
          <Item to="/search" icon="⌕" label="Búsqueda" />
          <Item icon="≡" label="Playlists" disabled />
          <Item icon="💬" label="Chat IA" disabled />
        </nav>
      </header>

      <main className="app-main">{children}</main>

      {/* Barra de reproductor viva (lee el estado global del reproductor). */}
      <PlayerBar />
    </div>
  );
}
