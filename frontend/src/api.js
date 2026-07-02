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

export function authHeaders() {
  return { Authorization: `Bearer ${getToken()}` };
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

// ─── Auth ────────────────────────────────────────────────────────────────────

// Pide al backend la URL de autorización de Spotify para arrancar el OAuth.
export async function getLoginUrl() {
  const res = await fetch(`${GATEWAY}/auth/login-url`);
  await ensureOk(res);
  return res.json(); // { url }
}
