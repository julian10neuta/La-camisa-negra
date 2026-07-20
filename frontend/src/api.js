// src/api.js
// ----------------------------------------------------------------------------
// Punto único para hablar con el backend a través del API Gateway.
// Antes cada página tenía la URL "quemada" (unas con localhost, otras con
// 127.0.0.1). Centralizarlo evita inconsistencias y repetición.
//
// Nota: usamos 127.0.0.1 (no localhost) para alinear con el dominio que Spotify
// exige en el redirect de OAuth. El gateway acepta ambos por CORS, pero así
// mantenemos todo en un solo host.
// ----------------------------------------------------------------------------

export const GATEWAY = "http://127.0.0.1:8000";

// El JWT propio de la app (no el token de Spotify). Lo guarda el Callback tras
// el login y lo usamos como Bearer en cada request protegida.
export function getToken() {
  return localStorage.getItem("token");
}

// El spotify_id va dentro del JWT (campo "sub"). Lo necesita el Web Playback SDK
// para pedir el token real de Spotify.
export function getSpotifyId() {
  const jwt = getToken();
  if (!jwt) return null;
  try {
    return JSON.parse(atob(jwt.split(".")[1])).sub;
  } catch {
    return null;
  }
}

export function authHeaders() {
  
  const headers = { Authorization: `Bearer ${getToken()}` };
  const spotifyId = getSpotifyId();
  if (spotifyId) {
    headers["x_spotify_id"] = spotifyId;
  }
  return headers;
  
  //return { Authorization: `Bearer ${getToken()}` };
}

// Lanza un error legible si la respuesta no es 2xx.
async function ensureOk(res) {
  if (!res.ok) {
    throw new Error(`El servidor respondió ${res.status}`);
  }
  return res;
}

// ─── Búsqueda ───────────────────────────────────────────────────────────────

// Devuelve una lista de canciones con metadata:
// { spotify_track_id, name, artist, album, cover_url, duration_ms }
export async function searchSongs(query, limit = 10) {
  const url = `${GATEWAY}/music/songs/search?q=${encodeURIComponent(query)}&limit=${limit}`;
  const res = await fetch(url, { headers: authHeaders() });
  await ensureOk(res);
  return res.json();
}

// ─── Likes (favoritos) ────────────────────────────────────────────────────────

export async function addLike(spotifyTrackId) {
  const res = await fetch(`${GATEWAY}/music/interactions/likes/${spotifyTrackId}`, {
    method: "POST",
    headers: authHeaders(),
  });
  return ensureOk(res);
}

export async function removeLike(spotifyTrackId) {
  const res = await fetch(`${GATEWAY}/music/interactions/likes/${spotifyTrackId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return ensureOk(res);
}

// Lista los favoritos del usuario. La usamos para saber qué canciones mostrar
// ya "marcadas" con el corazón al pintar resultados de búsqueda.
export async function listLikes() {
  const res = await fetch(`${GATEWAY}/music/interactions/likes`, {
    headers: authHeaders(),
  });
  await ensureOk(res);
  return res.json(); // [{ spotify_track_id }]
}

// ─── Dislikes ─────────────────────────────────────────────────────────────────
// Señal negativa fuerte para las recomendaciones. Es local (no se espeja en
// Spotify). Dar dislike quita el like y viceversa (lo maneja el backend).

export async function addDislike(spotifyTrackId) {
  const res = await fetch(`${GATEWAY}/music/interactions/dislikes/${spotifyTrackId}`, {
    method: "POST",
    headers: authHeaders(),
  });
  return ensureOk(res);
}

export async function removeDislike(spotifyTrackId) {
  const res = await fetch(`${GATEWAY}/music/interactions/dislikes/${spotifyTrackId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return ensureOk(res);
}

export async function listDislikes() {
  const res = await fetch(`${GATEWAY}/music/interactions/dislikes`, {
    headers: authHeaders(),
  });
  await ensureOk(res);
  return res.json(); // [{ spotify_track_id }]
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

// La pantalla del Dashboard entera en UNA llamada: los tres top-5 de la ventana,
// el resumen de escucha y las recomendaciones. Lo compone el dashboard_service
// llamando por dentro a music_service y recommendation_service, así que el
// navegador hace un viaje en vez de tres.
//
// Devuelve { window, top:{songs,artists,albums}, stats, recommendations, failed }.
// `failed` lista las secciones cuyo servicio falló: vienen a null y la pantalla
// debe decirlo en vez de pintar ceros, que mentirían.
//
//  - days   : ventana de las ESTADÍSTICAS (el diseño pide 24h y 7d -> 1 y 7)
//  - period : el de las RECOMENDACIONES (semanal/mensual), de los Ajustes.
//    Son cosas distintas: mirar tus stats de hoy no cambia tus recomendaciones.
export async function getDashboard({ days = 7, top = 5, period, limit } = {}) {
  const qs = new URLSearchParams({ days, top });
  if (period) qs.set("period", period);
  if (limit) qs.set("limit", limit);
  const res = await fetch(`${GATEWAY}/dashboard?${qs}`, { headers: authHeaders() });
  await ensureOk(res);
  return res.json();
}

// ─── Historial y estadísticas (Home) ──────────────────────────────────────────

// "Sigue escuchando": últimas canciones reproducidas, sin repetidos. Vienen con
// la misma forma que las recomendaciones (+ last_played), así que el reproductor
// las acepta tal cual.
export async function getHistory(limit = 8) {
  const res = await fetch(`${GATEWAY}/music/interactions/history?limit=${limit}`, {
    headers: authHeaders(),
  });
  await ensureOk(res);
  return res.json();
}

// "Tu semana en Wavely": { plays, distinct_songs, seconds_listened, top_artist,
// top_artist_plays, days, since }. Sale entero de nuestra base, sin tocar Spotify.
export async function getStats(days = 7) {
  const res = await fetch(`${GATEWAY}/music/interactions/stats?days=${days}`, {
    headers: authHeaders(),
  });
  await ensureOk(res);
  return res.json();
}

// ─── Reproducción ─────────────────────────────────────────────────────────────

// Reporta el resultado de una reproducción para alimentar las recomendaciones.
// El backend descarta lo que no supere el umbral de 30s (ver interaction_service).
// payload: { spotify_track_id, seconds_played, reached_end, was_skipped }
export async function registerPlayback(payload) {
  const res = await fetch(`${GATEWAY}/music/interactions/playback`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return ensureOk(res);
}

// El Web Playback SDK necesita el token REAL de Spotify (no el JWT de la app).
// Este endpoint del auth service lo entrega y lo refresca si hace falta.
export async function getSpotifyToken(spotifyId) {
  const res = await fetch(`${GATEWAY}/auth/tokens/${spotifyId}`);
  await ensureOk(res);
  const data = await res.json();
  return data.access_token;
}

// ─── Playlists ─────────────────────────────────────────────────────────────

export async function createPlaylist(name, description = "", isPublic = false) {
  const res = await fetch(`${GATEWAY}/music/playlists`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, public: isPublic }), // for now
  });
  await ensureOk(res);
  return res.json(); // { id, name }
}

export async function listPlaylists() {
  const res = await fetch(`${GATEWAY}/music/playlists`, {
    headers: authHeaders(),
  });
  await ensureOk(res)
  return res.json(); // [{id, name}]

}

export const getPlaylistTracksById = async (playlistId) => {
  const response = await fetch(`${GATEWAY}/music/playlists/${playlistId}/tracks`, {
    method: "GET",
    headers: authHeaders()
  });

  await ensureOk(response)
  return response.json();
}; // {id}

// ─── Recomendaciones ──────────────────────────────────────────────────────────

// `period` ("weekly"|"monthly") y `limit` salen de los Ajustes del usuario. Si no
// se pasan, el backend aplica sus defaults — por eso quien no los necesite (el
// reproductor, que solo quiere canciones para la cola) puede seguir llamando sin
// argumentos.
function recQuery({ period, limit } = {}) {
  const qs = new URLSearchParams();
  if (period) qs.set("period", period);
  if (limit) qs.set("limit", limit);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

// Devuelve { tracks, playlist_id, playlist_url, generated, period, last_updated,
// next_refresh }. Si hay una playlist reciente para ese período la devuelve tal
// cual; si no, la genera (puede tardar unos segundos porque consulta a Spotify).
// `next_refresh` lo calcula el backend, que es quien manda sobre la caducidad.
export async function getRecommendations(opts) {
  const res = await fetch(`${GATEWAY}/recommendations/list${recQuery(opts)}`, {
    headers: authHeaders(),
  });
  await ensureOk(res);
  return res.json();
}

// Fuerza la regeneración de las recomendaciones de ese período.
export async function refreshRecommendations(opts) {
  const res = await fetch(`${GATEWAY}/recommendations/refresh${recQuery(opts)}`, {
    method: "POST",
    headers: authHeaders(),
  });
  await ensureOk(res);
  return res.json();
}

// ─── Chat IA (RAG) ──────────────────────────────────────────────────────────

// Pregunta sobre una canción. El backend busca el artículo de Wikipedia que
// habla de ella y responde SOLO con eso, citando la fuente.
//
// Responde siempre 200 con un campo `mode` que dice qué pasó:
//   "answer"         -> { answer, source: {title, url, lang}, context_kind }
//   "no_context"     -> { message }  no hay información fiable de esa canción
//   "retrieval_only" -> { message, excerpt, source }  hay fuente pero no
//                       generador (falta la clave de Gemini o está caído)
// Por eso la página nunca trata la respuesta como un error: los tres casos son
// algo que mostrarle al usuario.
// `song` es opcional pero conviene mandarlo: la búsqueda del catálogo va
// directa a Spotify y no guarda nada en nuestra base, así que una canción recién
// buscada no existe ahí todavía. Mandando nombre y artista, el backend sabe
// igual de qué canción hablamos en vez de responder 404.
export async function askAboutSong(spotifyTrackId, question, song = null) {
  const res = await fetch(`${GATEWAY}/rag/ask`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({
      track_id: spotifyTrackId,
      question,
      name: song?.name ?? null,
      artist: song?.artist ?? null,
    }),
  });
  await ensureOk(res);
  return res.json();
}

// ─── Auth ────────────────────────────────────────────────────────────────────

// Pide al backend la URL de autorización de Spotify para arrancar el OAuth.
export async function getLoginUrl() {
  const res = await fetch(`${GATEWAY}/auth/login-url`);
  await ensureOk(res);
  return res.json(); // { url }
}
