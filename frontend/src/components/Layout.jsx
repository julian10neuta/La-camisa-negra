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

// Cerrar sesión: borra el JWT propio y los datos de usuario, y recarga en el
// login. Usamos una recarga completa (window.location) a propósito: así se
// desmonta el reproductor global (Web Playback SDK) y no queda música sonando
// ni estado de sesión residual. El logout es puramente de cliente porque el JWT
// es stateless (no hay endpoint que invalidar en el backend).
function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  window.location.href = "/";
}

export default function Layout({ children }) {
  return (
    <div className="app-shell">
      <header className="topnav">
        <Brand />
        <div className="topnav__right">
          <nav className="topnav__links">
            <Item to="/home" icon="⌂" label="Home" />
            <Item to="/dashboard" icon="▦" label="Dashboard" />
            <Item to="/search" icon="⌕" label="Búsqueda" />
            <Item icon="≡" label="Playlists" disabled />
            <Item icon="💬" label="Chat IA" disabled />
          </nav>
          <button className="btn-logout" onClick={logout} title="Cerrar sesión">
            <span aria-hidden="true">⎋</span> Cerrar sesión
          </button>
        </div>
      </header>

      <main className="app-main">{children}</main>

      {/* Barra de reproductor viva (lee el estado global del reproductor). */}
      <PlayerBar />
    </div>
  );
}
