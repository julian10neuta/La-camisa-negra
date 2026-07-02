// src/player/PlayerContext.jsx
// ----------------------------------------------------------------------------
// Estado GLOBAL de reproducción, compartido por toda la app (la barra inferior
// y la vista de reproducción leen de aquí). Vive al nivel de la app —no dentro
// de una página— para que la música siga sonando y su estado se conserve al
// navegar entre pantallas.
//
// Usa el Spotify Web Playback SDK, que crea un "dispositivo" en el navegador y
// exige cuenta Premium para producir audio. El SDK se carga de forma perezosa:
// solo cuando el usuario pulsa "reproducir" por primera vez (así el Login no
// carga nada).
//
// Decisiones de alcance (confirmadas):
//  - Se reproduce UNA sola canción por vez (sin cola) → siguiente/anterior inertes.
//  - Se registra la reproducción en el backend (play/skip por umbral de 30s).
// ----------------------------------------------------------------------------

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { getSpotifyId, getSpotifyToken, registerPlayback } from "../api";

const PlayerContext = createContext(null);

// eslint-disable-next-line react-refresh/only-export-components
export function usePlayer() {
  return useContext(PlayerContext);
}

const SDK_SRC = "https://sdk.scdn.co/spotify-player.js";
const END_TOLERANCE_MS = 1500; // margen para considerar que llegó al final

export function PlayerProvider({ children }) {
  // Estado que la UI observa
  const [current, setCurrent] = useState(null); // metadata de la canción actual
  const [paused, setPaused] = useState(true);
  const [position, setPosition] = useState(0); // ms
  const [duration, setDuration] = useState(0); // ms
  const [expanded, setExpanded] = useState(false); // overlay abierto
  const [ready, setReady] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Refs (no disparan re-render)
  const playerRef = useRef(null);
  const deviceIdRef = useRef(null);
  const initPromiseRef = useRef(null); // evita inicializar el SDK dos veces
  const tickRef = useRef(null); // intervalo que avanza la barra de progreso
  const reportRef = useRef(null); // { trackId, duration, reported } de lo que suena
  const progressedRef = useRef(false); // ¿la pista actual llegó a avanzar de verdad?

  // ─── Registro de reproducción (señal para recomendaciones) ─────────────────

  const reportPlayback = useCallback((seconds, reachedEnd, wasSkipped) => {
    const info = reportRef.current;
    if (!info || info.reported || !info.trackId) return;
    info.reported = true;
    // El backend descarta <30s, así que reportamos sin miedo a "ruido".
    registerPlayback({
      spotify_track_id: info.trackId,
      seconds_played: Math.floor(seconds),
      reached_end: reachedEnd,
      was_skipped: wasSkipped,
    }).catch(() => {
      /* no es bloqueante para la reproducción */
    });
  }, []);

  // ─── Ticker de progreso ────────────────────────────────────────────────────

  const stopTicker = useCallback(() => {
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  const startTicker = useCallback(() => {
    stopTicker();
    tickRef.current = setInterval(() => {
      setPosition((prev) => {
        const info = reportRef.current;
        const dur = info?.duration || 0;
        const next = prev + 1000;
        // Fallback de "llegó al final": si el ticker alcanza la duración y el
        // SDK no avisó, reportamos igual como reproducción completa.
        if (dur && next >= dur - END_TOLERANCE_MS && info && !info.reported) {
          reportPlayback(dur / 1000, true, false);
        }
        return dur ? Math.min(next, dur) : next;
      });
    }, 1000);
  }, [reportPlayback, stopTicker]);

  // ─── Inicialización perezosa del SDK ───────────────────────────────────────

  const ensureReady = useCallback(() => {
    if (ready && playerRef.current) return Promise.resolve(true);
    if (initPromiseRef.current) return initPromiseRef.current;

    const spotifyId = getSpotifyId();
    if (!spotifyId) {
      setErrorMsg("Inicia sesión para reproducir.");
      return Promise.reject(new Error("sin sesión"));
    }

    initPromiseRef.current = new Promise((resolve, reject) => {
      const onReadySDK = () => {
        const player = new window.Spotify.Player({
          name: "Wavely Web Player",
          // El SDK llama a esto cuando necesita un token fresco de Spotify.
          getOAuthToken: (cb) => {
            getSpotifyToken(spotifyId)
              .then((t) => cb(t))
              .catch(() => setErrorMsg("No se pudo obtener el token de Spotify."));
          },
          volume: 0.6,
        });
        playerRef.current = player;

        player.addListener("ready", ({ device_id }) => {
          deviceIdRef.current = device_id;
          setReady(true);
          resolve(true);
        });
        player.addListener("not_ready", () => setReady(false));
        player.addListener("account_error", () =>
          setErrorMsg("Tu cuenta de Spotify no es Premium: no se puede reproducir audio."));
        player.addListener("authentication_error", ({ message }) =>
          setErrorMsg("Error de autenticación con Spotify: " + message));
        player.addListener("initialization_error", ({ message }) =>
          setErrorMsg("No se pudo iniciar el reproductor: " + message));
        player.addListener("playback_error", ({ message }) =>
          setErrorMsg("Error de reproducción: " + message));

        // Fuente de verdad del estado real del reproductor.
        player.addListener("player_state_changed", (state) => {
          if (!state) return;
          setPaused(state.paused);
          setPosition(state.position);
          setDuration(state.duration);

          // Marcamos que la pista realmente avanzó (evita falsos "fin" al arrancar).
          if (state.position > 2000) progressedRef.current = true;

          // Detección de "canción terminada": el SDK deja position en 0 y
          // paused=true cuando la pista (sin cola) acaba. Solo cuenta si ya
          // había avanzado (si no, es el estado inicial, no un final).
          const info = reportRef.current;
          if (
            info &&
            !info.reported &&
            progressedRef.current &&
            state.paused &&
            state.position === 0 &&
            info.duration > 0
          ) {
            reportPlayback(info.duration / 1000, true, false);
          }
        });

        player.connect();
      };

      if (window.Spotify) {
        onReadySDK();
      } else {
        window.onSpotifyWebPlaybackSDKReady = onReadySDK;
        if (!document.getElementById("spotify-sdk")) {
          const script = document.createElement("script");
          script.id = "spotify-sdk";
          script.src = SDK_SRC;
          script.async = true;
          script.onerror = () => reject(new Error("no se pudo cargar el SDK"));
          document.body.appendChild(script);
        }
      }
    });

    return initPromiseRef.current;
  }, [ready, reportPlayback]);

  // ─── Acciones expuestas a la UI ────────────────────────────────────────────

  // Reproduce una canción (objeto con la metadata que ya trae la búsqueda).
  const playTrack = useCallback(
    async (track) => {
      setErrorMsg(null);

      // Si algo sonaba y no se ha reportado, cuenta como "saltada".
      reportPlayback(position / 1000, false, true);

      try {
        await ensureReady();
      } catch {
        return; // ensureReady ya dejó el mensaje de error
      }

      const deviceId = deviceIdRef.current;
      if (!deviceId) {
        setErrorMsg("El dispositivo de reproducción aún no está listo.");
        return;
      }

      // Preparamos el registro de ESTA nueva reproducción.
      reportRef.current = {
        trackId: track.spotify_track_id,
        duration: track.duration_ms || 0,
        reported: false,
      };
      progressedRef.current = false;

      // UI: mostramos la pista de inmediato. El progreso y el estado real
      // (paused) los marca el SDK vía player_state_changed —no de forma
      // optimista— para no contar reproducciones que nunca sonaron.
      setCurrent(track);
      setPosition(0);
      setDuration(track.duration_ms || 0);

      // Orden real a Spotify: reproducir en NUESTRO dispositivo.
      try {
        const token = await getSpotifyToken(getSpotifyId());
        const res = await fetch(
          `https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`,
          {
            method: "PUT",
            headers: {
              Authorization: "Bearer " + token,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ uris: [`spotify:track:${track.spotify_track_id}`] }),
          }
        );
        if (res.status !== 204) {
          setErrorMsg(`Spotify respondió ${res.status} al reproducir.`);
        }
      } catch {
        setErrorMsg("No se pudo enviar la orden de reproducción.");
      }
    },
    [ensureReady, position, reportPlayback]
  );

  const togglePlay = useCallback(async () => {
    if (!playerRef.current) return;
    await playerRef.current.togglePlay();
    // El estado real llega por player_state_changed; el ticker se ajusta abajo.
  }, []);

  const seek = useCallback(async (ms) => {
    if (!playerRef.current) return;
    await playerRef.current.seek(ms);
    setPosition(ms);
  }, []);

  // Arranca/detiene el ticker según pausa
  useEffect(() => {
    if (!current) return;
    if (paused) stopTicker();
    else startTicker();
  }, [paused, current, startTicker, stopTicker]);

  // Limpieza al desmontar la app
  useEffect(() => {
    return () => {
      stopTicker();
      if (playerRef.current) playerRef.current.disconnect();
    };
  }, [stopTicker]);

  const value = {
    current,
    paused,
    position,
    duration,
    expanded,
    ready,
    errorMsg,
    playTrack,
    togglePlay,
    seek,
    setExpanded,
  };

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}
