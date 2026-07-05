import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

export default function Callback() {
  const navigate = useNavigate();
  const called = useRef(false); // evita que useEffect corra dos veces en dev

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const error = params.get("error");

    if (error || !code) {
      navigate("/?error=spotify_denied");
      return;
    }

    fetch("http://127.0.0.1:8000/auth/callback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Error en autenticación");
        return res.json();
      })
      .then(async (data) => {
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("user", JSON.stringify(data.user));

        // Sincronizar liked songs de Spotify → nuestra BD
        // No bloqueamos la navegación si falla
        try {
          await fetch("http://127.0.0.1:8000/music/interactions/sync", {
            method: "POST",
            headers: { Authorization: `Bearer ${data.access_token}` },
          });
        } catch (e) {
          console.warn("Sync de liked songs falló, se reintentará en el próximo login:", e);
        }

        navigate("/dashboard");
      })
      .catch(() => {
        navigate("/?error=auth_failed");
      });
  }, [navigate]);

  return <p>Iniciando sesión...</p>;
}
