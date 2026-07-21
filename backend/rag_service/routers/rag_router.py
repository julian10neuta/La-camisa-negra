# rag_service/routers/rag_router.py
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from shared.database import get_db

from ..dependencies import get_redis
from ..repositories.song_repo import resolve_song
from ..services.answer_service import answer_question
from ..services.retriever import retrieve_context

router = APIRouter(prefix="/rag", tags=["rag"])

# Nota sobre `name`/`artist`: son opcionales y sirven de respaldo cuando la
# canción todavía no está en nuestra base de datos. Pasa constantemente, porque
# la búsqueda del catálogo va directa a Spotify y NO persiste nada (solo se
# guarda una canción cuando se crea una interacción con ella). Sin este respaldo,
# preguntar sobre un resultado del buscador daba 404.
NAME_HELP = "Nombre de la canción, por si aún no está en la base de datos"
ARTIST_HELP = "Artista, por si la canción aún no está en la base de datos"


class AskRequest(BaseModel):
    track_id: str = Field(..., description="spotify_track_id de la canción")
    question: str = Field(..., min_length=1, max_length=500)
    name: str | None = Field(None, max_length=300, description=NAME_HELP)
    artist: str | None = Field(None, max_length=300, description=ARTIST_HELP)


@router.get("/context")
async def get_context(
    track_id: str = Query(..., description="spotify_track_id de la canción"),
    name: str | None = Query(None, description=NAME_HELP),
    artist: str | None = Query(None, description=ARTIST_HELP),
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    El material de consulta de una canción: el texto de Wikipedia con el que
    luego el modelo tendrá permitido responder, y su fuente para citarla.

    Este endpoint es la mitad "recuperación" del RAG y funciona SOLO — sin
    clave de ningún modelo y sin costo. Sirve para comprobar lo difícil (que
    acertemos de qué canción se habla) antes de enchufar el generador.

    Responde 404 si la canción no está en nuestra base: solo sabemos hablar de
    canciones que el usuario ya escuchó o que le recomendamos.

    Si Wikipedia no tiene nada fiable, responde 200 con `found: false` — no es
    un error, es la respuesta honesta.
    """
    song = resolve_song(db, track_id, name, artist)
    if song is None:
        raise HTTPException(
            status_code=404,
            detail="No sé de qué canción se trata: no está en la base de datos "
            "y no me mandaste nombre y artista.",
        )

    context = await retrieve_context(
        song_name=song.name,
        artist=song.artist,
        track_id=track_id,
        redis=redis,
    )

    return {
        "song": {
            "spotify_track_id": song.spotify_track_id,
            "name": song.name,
            "artist": song.artist,
        },
        **context,
    }


@router.post("/ask")
async def ask(
    body: AskRequest,
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Pregunta sobre una canción. Es el endpoint que usa la pantalla de Chat.

    Siempre responde 200 con un campo `mode` que dice qué pasó:

      - `answer`         : hay respuesta redactada, con su `source` para citar.
      - `no_context`     : no hay información fiable de esa canción. No se
                           consulta al modelo, para que no invente.
      - `retrieval_only` : hay material pero no generador (falta la clave o
                           Gemini no responde); va un `excerpt` de la fuente.

    Solo 404 si no hay forma de saber de qué canción se habla (ni está en la
    base de datos ni vinieron `name` y `artist`).
    """
    song = resolve_song(db, body.track_id, body.name, body.artist)
    if song is None:
        raise HTTPException(
            status_code=404,
            detail="No sé de qué canción se trata: no está en la base de datos "
            "y no me mandaste nombre y artista.",
        )

    result = await answer_question(song, body.question, redis=redis)

    return {
        "song": {
            "spotify_track_id": song.spotify_track_id,
            "name": song.name,
            "artist": song.artist,
        },
        "question": body.question,
        **result,
    }
