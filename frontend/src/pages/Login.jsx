// src/pages/Login.jsx
// ----------------------------------------------------------------------------
// Pantalla de inicio de sesión (diseño Wavely). El login está 100% delegado a
// Spotify vía OAuth 2.0: esta pantalla solo arranca el flujo (pide la URL de
// autorización al backend y redirige) y avisa si hubo cancelación/error para
// reintentar.
// ----------------------------------------------------------------------------

import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { getLoginUrl, getToken } from "../api";

// Barras decorativas del fondo (alturas variadas para el efecto de ecualizador).
function AudioBars() {
  const bars = Array.from({ length: 40 });
  return (
    <div className="audio-bars" aria-hidden="true">
      {bars.map((_, i) => (
        <span key={i} style={{ animationDelay: `${(i % 10) * 0.12}s` }} />
      ))}
    </div>
  );
}

export default function Login() {
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState(null);
  const [params] = useSearchParams();
  const navigate = useNavigate();

  // Si Callback nos devolvió aquí con ?error=..., mostramos el aviso.
  const oauthError = params.get("error");

  // Si ya hay sesión activa (y no venimos de un error de OAuth), entramos
  // directo al Home apenas se abre la app, sin pasar por esta pantalla.
  useEffect(() => {
    if (getToken() && !oauthError) navigate("/home", { replace: true });
  }, [navigate, oauthError]);

  const handleLogin = async () => {
    setError(null);
    setRedirecting(true);
    try {
      const { url } = await getLoginUrl();
      window.location.href = url; // salimos de la SPA hacia Spotify
    } catch {
      setRedirecting(false);
      setError("No se pudo iniciar el proceso. Inténtalo de nuevo.");
    }
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <span className="brand">
          <span className="brand__badge">♪</span>
          Wavely
        </span>

        <p className="login-tagline">
          Streaming musical con recomendaciones personalizadas y tu asistente de
          música con IA
        </p>

        {(error || oauthError) && (
          <div className="login-error">
            {error ||
              "El inicio de sesión con Spotify no se completó. Puedes intentarlo de nuevo."}
          </div>
        )}

        {redirecting ? (
          <>
            <div className="login-progress" />
            <p className="login-note">Redirigiendo a Spotify…</p>
            <p className="login-note">Por favor, no cierres esta ventana.</p>
          </>
        ) : (
          <>
            <button className="btn" onClick={handleLogin}>
              <span aria-hidden="true">●</span> Iniciar sesión con Spotify
            </button>
            <p className="login-note">
              Al continuar, serás redirigido a Spotify para autenticarte de forma
              segura.
            </p>
          </>
        )}
      </div>

      <p className="login-disclaimer">
        Wavely usa la API de Spotify exclusivamente para autenticación y acceso al
        catálogo musical. No almacenamos tu contraseña.
      </p>

      <AudioBars />
    </div>
  );
}
