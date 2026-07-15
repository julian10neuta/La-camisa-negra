# backend/scripts/backfill_song_album.py
# ----------------------------------------------------------------------------
# Rellena `album` y `cover_url` en las canciones que se guardaron ANTES de que
# esas columnas volvieran a existir (ver migración b1c4e7d9f2a3).
#
# Se ejecuta UNA vez, a mano, después de aplicar la migración:
#
#     docker exec la_camisa_negra_music python -m scripts.backfill_song_album
#
# Cuesta una llamada a Spotify por canción, porque el lote /tracks?ids= devuelve
# 403 para esta app. Por eso:
#   - Solo toca las filas a las que les falta el dato (es idempotente: si se
#     ejecuta dos veces, la segunda no hace ninguna llamada).
#   - Va despacio a propósito (PAUSA_SEGUNDOS): esto no corre en la ruta de una
#     petición, no hay prisa, y una ráfaga es justo lo que ya nos costó dos baneos.
#   - Si Spotify responde 429, para en seco en vez de insistir.
#
# Las canciones nuevas NO lo necesitan: desde ahora
# SongRepository.create_from_spotify_data guarda los dos campos al crearlas.
# ----------------------------------------------------------------------------

import asyncio
import sys

import httpx

from shared.database import SessionLocal
from shared.models import Song, User
from shared.spotify_service import SpotifyService
from shared.token_service import TokenService
from shared.redis import get_redis_client
from music_service.repositories.song_repository import SongRepository

PAUSA_SEGUNDOS = 0.5


async def main() -> int:
    db = SessionLocal()
    redis = get_redis_client()
    try:
        pendientes = (
            db.query(Song)
            .filter((Song.album.is_(None)) | (Song.cover_url.is_(None)))
            .all()
        )
        if not pendientes:
            print("Nada que hacer: todas las canciones ya tienen álbum y carátula.")
            return 0

        # Cualquier usuario sirve: el token es para leer el catálogo, que es
        # público e igual para todos.
        user = db.query(User).first()
        if not user:
            print("No hay usuarios en la base; sin token no se puede consultar a Spotify.")
            return 1

        try:
            token = await TokenService(redis).get_token(user.spotify_id)
        except Exception as e:
            print(f"No se pudo obtener un token de Spotify: {e}")
            return 1

        spotify = SpotifyService()
        ok = fallidas = 0
        print(f"{len(pendientes)} canciones por rellenar.\n")

        for i, song in enumerate(pendientes, 1):
            try:
                track = await spotify.get_track(song.spotify_track_id, token)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry = e.response.headers.get("Retry-After", "?")
                    print(f"\nSpotify nos está limitando (429). Retry-After: {retry}s.")
                    print(f"Paramos aquí. Hecho: {ok}. Vuelve a lanzarlo cuando se levante:")
                    print("seguirá justo por donde se quedó.")
                    return 2
                print(f"  [{i}/{len(pendientes)}] {song.name}: HTTP {e.response.status_code}")
                fallidas += 1
                continue
            except Exception as e:
                print(f"  [{i}/{len(pendientes)}] {song.name}: {e}")
                fallidas += 1
                continue

            SongRepository.backfill_album_and_cover(db, song, track)
            estado = "✓" if song.cover_url else "sin carátula"
            print(f"  [{i}/{len(pendientes)}] {song.name} — {song.album or '?'} {estado}")
            ok += 1
            await asyncio.sleep(PAUSA_SEGUNDOS)

        print(f"\nListo. Rellenadas: {ok}. Fallidas: {fallidas}.")
        return 0
    finally:
        db.close()
        redis.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
