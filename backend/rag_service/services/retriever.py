# rag_service/services/retriever.py
# La "R" de RAG: RECUPERACIÓN. Dada una canción, consigue el texto con el que
# más adelante el modelo tendrá permitido responder — y solo con ese.
#
# El recorrido es corto a propósito:
#
#   spotify_track_id  ->  (base de datos local)   nombre + artista
#                     ->  (Wikipedia: buscar)     candidatos
#                     ->  (resolver.py)           ¿cuál es? ¿o ninguno?
#                     ->  (Wikipedia: extraer)    el texto del artículo
#
# REGLA DE RECURSOS (la lección del bloqueo de Spotify): aquí NO se dispara nada
# al cargar una pantalla ni al listar recomendaciones. Solo se llama a Wikipedia
# cuando el usuario abre el chat de UNA canción concreta. Y lo que se trae se
# cachea, así que una canción se busca una sola vez en la vida.
import json

from .resolver import clean_song_title, pick_best, pick_best_artist, _first_artist
from .wikipedia_client import LANGS, WikipediaClient

# Cuánto vive lo cacheado. Los artículos cambian poco, así que un mes es sano.
TTL_FOUND = 60 * 60 * 24 * 30      # 30 días
# Los "no encontrado" caducan antes: si mañana crean el artículo de esa canción,
# queremos enterarnos sin esperar un mes.
TTL_NOT_FOUND = 60 * 60 * 24       # 1 día


def _cache_key(track_id: str) -> str:
    return f"rag:context:{track_id}"


async def retrieve_context(
    song_name: str,
    artist: str,
    track_id: str,
    redis=None,
    client: WikipediaClient | None = None,
) -> dict:
    """
    Devuelve el contexto de una canción:

        {
          "found":  bool,
          "kind":   "song" | "artist" | None,   # de qué es el artículo
          "source": {"title", "url", "lang"} | None,
          "text":   str,                        # vacío si no se encontró
          "cached": bool,
        }

    `kind` importa para el prompt: si el artículo es del ARTISTA y no de la
    canción, el modelo debe saberlo para no atribuirle a la canción cosas que
    el texto dice del artista en general.
    """
    if redis is not None:
        hit = redis.get(_cache_key(track_id))
        if hit:
            return {**json.loads(hit), "cached": True}

    result = await _retrieve_fresh(song_name, artist, client or WikipediaClient())

    if redis is not None:
        ttl = TTL_FOUND if result["found"] else TTL_NOT_FOUND
        redis.setex(_cache_key(track_id), ttl, json.dumps(result))

    return {**result, "cached": False}


async def _retrieve_fresh(song_name: str, artist: str, client: WikipediaClient) -> dict:
    clean_song = clean_song_title(song_name)
    main_artist = _first_artist(artist)

    # 1) El artículo de la CANCIÓN, idioma por idioma.
    for lang in LANGS:
        candidates = await client.search(lang, f'"{clean_song}" {main_artist}')
        best = pick_best(candidates, clean_song, artist)
        if best:
            article = await client.get_extract(lang, best["title"])
            if article:
                return _as_context(article, kind="song")

    # 2) Plan B: el artículo del ARTISTA. Peor que el de la canción, pero deja
    #    responder sobre estilo, trayectoria y contexto en vez de no decir nada.
    #    Las canciones de descubrimiento suelen caer aquí.
    for lang in LANGS:
        candidates = await client.search(lang, main_artist)
        best = pick_best_artist(candidates, artist)
        if best:
            article = await client.get_extract(lang, best["title"])
            if article:
                return _as_context(article, kind="artist")

    # 3) Nada fiable. Se dice, no se inventa.
    return {"found": False, "kind": None, "source": None, "text": ""}


def _as_context(article: dict, kind: str) -> dict:
    return {
        "found": True,
        "kind": kind,
        "source": {
            "title": article["title"],
            "url": article["url"],
            "lang": article["lang"],
        },
        "text": article["text"],
    }
