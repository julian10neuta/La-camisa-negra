# rag_service/services/answer_service.py
# Junta las dos mitades del RAG: recupera el texto y luego genera la respuesta.
# El router se queda fino y toda la decisión vive aquí.
#
# Hay tres desenlaces posibles y los tres son respuestas válidas, no errores:
#
#   "answer"          -> Wikipedia tenía material y Gemini redactó con él.
#   "unsourced"       -> no había artículo, así que Gemini responde con lo que
#                        sepa por su cuenta. Se marca como tal de arriba abajo.
#   "retrieval_only"  -> sí hay material pero no hay generador (falta la clave o
#                        Gemini está caído). Devolvemos el texto y la fuente para
#                        que el usuario lea por su cuenta.
#   "no_context"      -> ni fuente ni generador. Lo único que queda es decirlo.
#
# En el modo "answer" la respuesta puede venir partida en dos: `answer` es lo
# que se apoya en el artículo, y `own_reading` lo que el modelo aporta por su
# cuenta. Se separan aquí, en el backend, y la interfaz los pinta distinto: el
# usuario tiene que poder ver de un vistazo qué es comprobable y qué no.
import hashlib
import json

from .generator import (
    MARCA_LECTURA,
    GeneratorUnavailable,
    generate,
    generate_unsourced,
    is_configured,
)
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

    datos_cancion = {"name": song.name, "artist": song.artist}

    if not context["found"]:
        # Sin artículo no hay nada que comprobar, pero callarse del todo tampoco
        # ayuda: dejamos que el modelo responda con lo suyo, marcado como tal.
        try:
            result = await generate_unsourced(question, datos_cancion)
        except GeneratorUnavailable:
            return _no_context(song)

        payload = {
            "mode": "unsourced",
            "answer": None,
            "own_reading": result["answer"],
            "model": result["model"],
            "source": None,
            "message": (
                "No encontré ninguna fuente sobre esta canción, así que esto es "
                "solo lo que sabe la IA. No puedo garantizarte que sea exacto."
            ),
        }
        if redis is not None:
            redis.setex(
                _answer_key(song.spotify_track_id, question),
                TTL_ANSWER,
                json.dumps(payload),
            )
        return {**payload, "cached": False}

    if not is_configured():
        return _retrieval_only(context, motivo="sin_clave")

    try:
        result = await generate(question, context, datos_cancion)
    except GeneratorUnavailable:
        return _retrieval_only(context, motivo="generador_no_disponible")

    apoyado, propio = _separar_lectura(result["answer"])

    payload = {
        "mode": "answer",
        "answer": apoyado,
        "own_reading": propio,
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


def _separar_lectura(texto: str) -> tuple[str, str | None]:
    """
    Parte la respuesta por la marca que el modelo pone antes de lo que aporta
    por su cuenta. Si no la puso —que es lo normal cuando no tenía nada que
    añadir— todo cuenta como apoyado en el artículo.
    """
    if MARCA_LECTURA not in texto:
        return texto.strip(), None

    apoyado, _, propio = texto.partition(MARCA_LECTURA)
    return apoyado.strip(), propio.strip() or None


def _no_context(song) -> dict:
    """Ni fuente ni generador: solo queda decirlo."""
    return {
        "mode": "no_context",
        "answer": None,
        "source": None,
        "message": (
            f"No encontré información confiable sobre «{song.name}» de "
            f"{song.artist}, y ahora mismo tampoco puedo consultar a la IA."
        ),
        "cached": False,
    }


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
