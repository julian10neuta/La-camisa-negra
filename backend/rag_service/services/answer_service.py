# rag_service/services/answer_service.py
# Junta las dos mitades del RAG: recupera el texto y luego genera la respuesta.
# El router se queda fino y toda la decisión vive aquí.
#
# Hay tres desenlaces posibles y los tres son respuestas válidas, no errores:
#
#   "answer"          -> Wikipedia tenía material y Gemini redactó con él.
#   "no_context"      -> no encontramos nada fiable de esa canción. NO se llama
#                        a Gemini: sin texto solo podría inventar, que es justo
#                        lo que este diseño existe para evitar. Y de paso no
#                        gastamos cuota.
#   "retrieval_only"  -> sí hay material pero no hay generador (falta la clave o
#                        Gemini está caído). Devolvemos el texto y la fuente para
#                        que el usuario lea por su cuenta.
import hashlib
import json

from .generator import GeneratorUnavailable, generate, is_configured
from .retriever import retrieve_context

TTL_ANSWER = 60 * 60 * 24 * 30      # 30 días

# Cuánto texto de la fuente devolvemos cuando no hay generador. Lo justo para
# que se pueda leer en pantalla sin volcar el artículo entero.
EXCERPT_CHARS = 1200


def _answer_key(track_id: str, question: str) -> str:
    # La pregunta se normaliza y se resume con un hash: dos usuarios que
    # pregunten lo mismo con distinta capitalización comparten la respuesta, y
    # la clave de Redis no depende del largo de la pregunta.
    normal = " ".join(question.lower().split())
    digest = hashlib.sha1(normal.encode("utf-8")).hexdigest()[:16]
    return f"rag:answer:{track_id}:{digest}"


async def answer_question(song, question: str, redis=None) -> dict:
    """
    `song` es el modelo Song de la base de datos; `question` lo que escribió el
    usuario. Devuelve siempre un dict con "mode", y con "answer"/"source"
    cuando corresponda.
    """
    if redis is not None:
        hit = redis.get(_answer_key(song.spotify_track_id, question))
        if hit:
            return {**json.loads(hit), "cached": True}

    context = await retrieve_context(
        song_name=song.name,
        artist=song.artist,
        track_id=song.spotify_track_id,
        redis=redis,
    )

    if not context["found"]:
        # Nada que consultar: se dice y se acabó. Sin llamar al modelo.
        return {
            "mode": "no_context",
            "answer": None,
            "source": None,
            "message": (
                f"No encontré información confiable sobre «{song.name}» de "
                f"{song.artist}. Prefiero decírtelo a inventarme una respuesta."
            ),
            "cached": False,
        }

    if not is_configured():
        return _retrieval_only(context, motivo="sin_clave")

    try:
        result = await generate(question, context, {"name": song.name, "artist": song.artist})
    except GeneratorUnavailable:
        return _retrieval_only(context, motivo="generador_no_disponible")

    payload = {
        "mode": "answer",
        "answer": result["answer"],
        "model": result["model"],
        "source": context["source"],
        "context_kind": context["kind"],
    }

    if redis is not None:
        redis.setex(
            _answer_key(song.spotify_track_id, question),
            TTL_ANSWER,
            json.dumps(payload),
        )

    return {**payload, "cached": False}


def _retrieval_only(context: dict, motivo: str) -> dict:
    """
    No se cachea: la falta de generador es temporal (falta la clave, o Gemini
    está saturado). Si lo guardáramos, el usuario seguiría viendo el modo
    degradado un mes después de arreglarlo.
    """
    return {
        "mode": "retrieval_only",
        "answer": None,
        "reason": motivo,
        "source": context["source"],
        "context_kind": context["kind"],
        "excerpt": context["text"][:EXCERPT_CHARS],
        "message": (
            "Encontré información sobre esta canción, pero ahora mismo no puedo "
            "redactarte la respuesta. Te dejo lo que dice la fuente."
        ),
        "cached": False,
    }
