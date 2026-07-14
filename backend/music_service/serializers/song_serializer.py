
def _serialize_track(track: dict) -> dict:
    """
    Aplana el objeto crudo de Spotify a solo los campos que el frontend
    necesita para pintar un resultado de búsqueda (diseño de la pantalla
    Search): carátula, título, artista, álbum y duración.

    Todos estos campos son metadata básica de catálogo que Spotify sigue
    entregando en /v1/search — NO son las 'audio features' restringidas
    desde nov-2024. No se persisten: se devuelven en vivo tal como llegan.
    """
    artists = track.get("artists") or []
    album = track.get("album") or {}
    images = album.get("images") or []

    return {
        "spotify_track_id": track["id"],
        "name": track.get("name", "Unknown"),
        "artist": artists[0]["name"] if artists else "Unknown",
        "album": album.get("name"),
        # images viene ordenado de mayor a menor; la primera es la de más resolución
        "cover_url": images[0]["url"] if images else None,
        "duration_ms": track.get("duration_ms"),
    }