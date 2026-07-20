# rag_service/routers/rag_router.py
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from shared.database import get_db

from ..dependencies import get_redis
from ..repositories.song_repo import get_song_by_track_id
from ..services.answer_service import answer_question
from ..services.retriever import retrieve_context

router = APIRouter(prefix="/rag", tags=["rag"])


class AskRequest(BaseModel):
    track_id: str = Field(..., description="spotify_track_id de la canción")
    question: str = Field(..., min_length=1, max_length=500)


@router.get("/context")
async def get_context(
    track_id: str = Query(..., description="spotify_track_id de la canción"),
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
    song = get_song_by_track_id(db, track_id)
    if song is None:
        raise HTTPException(
            status_code=404,
            detail="Esa canción no está en la biblioteca de la aplicación.",
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

    Solo 404 si la canción no está en nuestra base de datos.
    """
    song = get_song_by_track_id(db, body.track_id)
    if song is None:
        raise HTTPException(
            status_code=404,
            detail="Esa canción no está en la biblioteca de la aplicación.",
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
