// src/player/PlayerContext.jsx
// ----------------------------------------------------------------------------
// Estado GLOBAL de reproducción (barra inferior + vista de reproducción leen de
// aquí). Vive al nivel de la app para que la música siga sonando al navegar.
//
// Usa el Spotify Web Playback SDK (exige Premium; se carga perezoso al 1er play).
//
// COLA (siguiente/anterior) — dos modos:
//  - "playlist": cola FINITA (p. ej. el Dashboard de recomendaciones). Avanza sola
//     y PARA cuando se acaba.
//  - "search": al reproducir desde el buscador, tras la canción buscada la cola se
//     arma con Me gusta (70%) + recomendaciones (30%) mezcladas al azar.
//
// Cada reproducción se registra en el backend (play/skip por umbral de 30s).
// ----------------------------------------------------------------------------

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import {
  getSpotifyId,
  getSpotifyToken,
  registerPlayback,
  listLikes,
  getRecommendations,
} from "../api";
import { useSettings } from "../settings/SettingsContext";

const PlayerContext = createContext(null);

// eslint-disable-next-line react-refresh/only-export-components
export function usePlayer() {
  return useContext(PlayerContext);
}

const SDK_SRC = "https://sdk.scdn.co/spotify-player.js";
const END_TOLERANCE_MS = 1500; // margen para considerar que llegó al final
const LIKES_RATIO = 0.7; // 70% Me gusta / 30% recomendadas en el mix del buscador

// Fisher-Yates
function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Construye una cola de Me gusta (70%) + recomendaciones (30%) mezcladas
// aleatoriamente, sin repetidos ni la canción semilla. Los "Me gusta" solo traen id
// (el SDK rellena título/carátula al reproducir); las recomendaciones traen metadata.
//
// La usan dos cosas: la cola del buscador y, si el usuario tiene el autoplay
// activado, la prolongación de la cola cuando se agota. `excludeIds` sirve para
// ese segundo caso: lo que acabas de escuchar no debería volver a sonar de
// inmediato.
async function buildSearchMix(seedTrack, excludeIds = [], recOpts = undefined) {
  const [likes, recs] = await Promise.all([
    listLikes().catch(() => []),
    // recOpts lleva el período y el número que el usuario tiene en Ajustes. Sin
    // ellos pediríamos los del backend (semanal), y a alguien que eligió
    // "mensual" le dispararíamos la generación de una lista semanal que no ha
    // pedido: ~17s y una playlist nueva en su Spotify para nada.
    getRecommendations(recOpts).then((r) => r.tracks || []).catch(() => []),
  ]);
  const seen = new Set([seedTrack.spotify_track_id, ...excludeIds]);
  const likePool = shuffle(
    likes.map((l) => ({ spotify_track_id: l.spotify_track_id }))
  ).filter((t) => !seen.has(t.spotify_track_id));
  const recPool = shuffle(recs).filter((t) => !seen.has(t.spotify_track_id));

  const mix = [];
  while (likePool.length || recPool.length) {
    let pickLike;
    if (!likePool.length) pickLike = false;
    else if (!recPool.length) pickLike = true;
    else pickLike = Math.random() < LIKES_RATIO;
    const t = pickLike ? likePool.shift() : recPool.shift();
    if (t && !seen.has(t.spotify_track_id)) {
      seen.add(t.spotify_track_id);
      mix.push(t);
    }
  }
  return mix;
}

export function PlayerProvider({ children }) {
  // Estado que la UI observa
  const [current, setCurrent] = useState(null);
  const [paused, setPaused] = useState(true);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [ready, setReady] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Refs (no disparan re-render)
  const playerRef = useRef(null);
  const deviceIdRef = useRef(null);
  const initPromiseRef = useRef(null);
  const tickRef = useRef(null);
  const reportRef = useRef(null); // { trackId, duration, reported }
  const progressedRef = useRef(false);
  const positionRef = useRef(0); // espejo de position (para leerlo sin closures viejos)

  // Cola de reproducción
  const queueRef = useRef([]); // lista de tracks
  const indexRef = useRef(0); // posición actual en la cola
  const modeRef = useRef(null); // "playlist" | "search"
  const searchBuildRef = useRef(null); // promesa de construcción del mix del buscador
  const autoAdvanceRef = useRef(null); // apunta siempre al next() más reciente

  // Espejo de los ajustes, por el mismo motivo que positionRef: next() se llama
  // desde listeners del SDK, y leer el estado ahí daría el valor viejo.
  const { settings } = useSettings();
  const settingsRef = useRef(settings);
  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  // Opciones de recomendaciones para el mix (período y número del usuario).
  const recOpts = () => ({
    period: settingsRef.current.period,
    limit: settingsRef.current.recCount,
  });

  // ─── Registro de reproducción ──────────────────────────────────────────────

  const reportPlayback = useCallback((seconds, reachedEnd, wasSkipped) => {
    const info = reportRef.current;
    if (!info || info.reported || !info.trackId) return false;
    info.reported = true;
    registerPlayback({
      spotify_track_id: info.trackId,
      seconds_played: Math.floor(seconds),
      reached_end: reachedEnd,
      was_skipped: wasSkipped,
    }).catch(() => {});
    return true; // sí reportó (para disparar auto-avance una sola vez)
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
        const nextPos = dur ? Math.min(prev + 1000, dur) : prev + 1000;
        positionRef.current = nextPos;
        // Fallback de "llegó al final": si el ticker alcanza la duración y el SDK
        // no avisó, reportamos y auto-avanzamos.
        if (dur && nextPos >= dur - END_TOLERANCE_MS && info && !info.reported) {
          if (reportPlayback(dur / 1000, true, false)) autoAdvanceRef.current?.();
        }
        return nextPos;
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

        player.addListener("player_state_changed", (state) => {
          if (!state) return;
          setPaused(state.paused);
          setPosition(state.position);
          positionRef.current = state.position;
          setDuration(state.duration);
          if (state.position > 2000) progressedRef.current = true;

          // Rellena/actualiza la metadata mostrada desde el SDK (útil para los
          // "Me gusta", que entran en la cola solo con id).
          const ct = state.track_window?.current_track;
          if (ct) {
            setCurrent((prev) => {
              if (prev && prev.spotify_track_id === ct.id && prev.name) return prev;
              return {
                spotify_track_id: ct.id,
                name: ct.name,
                artist: (ct.artists || []).map((a) => a.name).join(", "),
                cover_url: ct.album?.images?.[0]?.url || null,
                duration_ms: ct.duration_ms || 0,
              };
            });
          }

          // "Canción terminada": el SDK deja position 0 y paused=true. Solo cuenta
          // si ya había avanzado. Reportamos y auto-avanzamos (una sola vez).
          const info = reportRef.current;
          if (
            info &&
            !info.reported &&
            progressedRef.current &&
            state.paused &&
            state.position === 0 &&
            info.duration > 0
          ) {
            if (reportPlayback(info.duration / 1000, true, false)) autoAdvanceRef.current?.();
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

  // ─── Reproducir la pista en el índice dado de la cola ──────────────────────

  const playAt = useCallback(
    async (i) => {
      const q = queueRef.current;
      if (i < 0 || i >= q.length) return;
      const track = q[i];
      indexRef.current = i;
      setErrorMsg(null);

      // Reporta la saliente como "saltada" (no-op si ya se reportó por fin natural).
      reportPlayback(positionRef.current / 1000, false, true);

      try {
        await ensureReady();
      } catch {
        return;
      }
      const deviceId = deviceIdRef.current;
      if (!deviceId) {
        setErrorMsg("El dispositivo de reproducción aún no está listo.");
        return;
      }

      reportRef.current = {
        trackId: track.spotify_track_id,
        duration: track.duration_ms || 0,
        reported: false,
      };
      progressedRef.current = false;

      // Display: si tenemos metadata la mostramos ya; si no (Me gusta = solo id),
      // el SDK la rellena en player_state_changed.
      setCurrent(
        track.name
          ? track
          : { spotify_track_id: track.spotify_track_id, name: null, artist: "", cover_url: null, duration_ms: track.duration_ms || 0 }
      );
      setPosition(0);
      positionRef.current = 0;
      setDuration(track.duration_ms || 0);

      try {
        const token = await getSpotifyToken(getSpotifyId());
        const res = await fetch(
          `https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`,
          {
            method: "PUT",
            headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
            body: JSON.stringify({ uris: [`spotify:track:${track.spotify_track_id}`] }),
          }
        );
        if (res.status !== 204) setErrorMsg(`Spotify respondió ${res.status} al reproducir.`);
      } catch {
        setErrorMsg("No se pudo enviar la orden de reproducción.");
      }
    },
    [ensureReady, reportPlayback]
  );

  // ─── Acciones públicas ─────────────────────────────────────────────────────

  // context:
  //   { queue: [...], index: n }  → modo playlist (Dashboard/recomendaciones)
  //   { mode: "search" }           → modo buscador (arma el mix Me gusta+recs)
  //   (nada)                       → una sola canción
  const playTrack = useCallback(
    async (track, context = {}) => {
      if (Array.isArray(context.queue)) {
        modeRef.current = "playlist";
        queueRef.current = context.queue;
        searchBuildRef.current = null;
        await playAt(context.index ?? 0);
      } else if (context.mode === "search") {
        modeRef.current = "search";
        queueRef.current = [track];
        // Construimos el mix en segundo plano; no bloquea la reproducción.
        searchBuildRef.current = buildSearchMix(track, [], recOpts())
          .then((mix) => {
            queueRef.current = [track, ...mix];
          })
          .catch(() => {});
        await playAt(0);
      } else {
        modeRef.current = "playlist";
        queueRef.current = [track];
        searchBuildRef.current = null;
        await playAt(0);
      }
    },
    [playAt]
  );

  const next = useCallback(async () => {
    // En el buscador, si aún no hay siguiente, esperamos a que el mix termine.
    if (
      indexRef.current + 1 >= queueRef.current.length &&
      modeRef.current === "search" &&
      searchBuildRef.current
    ) {
      try {
        await searchBuildRef.current;
      } catch {
        /* ignore */
      }
    }
    if (indexRef.current + 1 < queueRef.current.length) {
      await playAt(indexRef.current + 1);
      return;
    }

    // Se acabó la cola. Con el autoplay activado (Ajustes) la prolongamos con un
    // mix de tus Me gusta y tus recomendaciones, excluyendo lo que acabas de oír,
    // en vez de cortar la música. Con el autoplay apagado, para — que era el
    // comportamiento de siempre.
    const seed = queueRef.current[indexRef.current];
    if (settingsRef.current.autoplay && seed) {
      const yaSonaron = queueRef.current.map((t) => t.spotify_track_id);
      const mix = await buildSearchMix(seed, yaSonaron, recOpts()).catch(() => []);
      if (mix.length) {
        queueRef.current = [...queueRef.current, ...mix];
        await playAt(indexRef.current + 1);
        return;
      }
      // Sin nada que añadir (usuario sin likes ni recomendaciones): paramos igual.
    }

    if (playerRef.current) {
      await playerRef.current.pause(); // fin de la cola → parar
    }
  }, [playAt]);

  const seek = useCallback(async (ms) => {
    if (!playerRef.current) return;
    await playerRef.current.seek(ms);
    setPosition(ms);
    positionRef.current = ms;
  }, []);

  const prev = useCallback(async () => {
    if (positionRef.current > 3000) {
      await seek(0); // llevas rato: reinicia la actual
    } else if (indexRef.current > 0) {
      await playAt(indexRef.current - 1);
    } else {
      await seek(0);
    }
  }, [playAt, seek]);

  const togglePlay = useCallback(async () => {
    if (playerRef.current) await playerRef.current.togglePlay();
  }, []);

  // autoAdvanceRef siempre apunta al next() vigente (se usa dentro de listeners).
  useEffect(() => {
    autoAdvanceRef.current = next;
  }, [next]);

  // Arranca/detiene el ticker según pausa
  useEffect(() => {
    if (!current) return;
    if (paused) stopTicker();
    else startTicker();
  }, [paused, current, startTicker, stopTicker]);

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
    next,
    prev,
    setExpanded,
  };

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}
