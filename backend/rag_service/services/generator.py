# rag_service/services/generator.py
# La "G" de RAG: GENERACIÓN. Le pasa a Gemini la pregunta del usuario junto con
# el texto que recuperamos de Wikipedia, y le prohíbe responder con cualquier
# otra cosa.
#
# Esa prohibición es el punto entero del RAG. Un modelo suelto contesta sobre
# cualquier canción con total seguridad, y cuando no sabe, se lo inventa con la
# misma seguridad. Aquí solo puede usar el texto que le dimos, y tiene que citar
# de dónde salió, así tú puedes comprobarlo.
#
# Se usa la API REST con httpx, que ya es dependencia del proyecto: no hace falta
# instalar el SDK de Google.
import httpx

from shared.config import settings

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Si el modelo configurado está caído o cerrado, se prueban estos por orden.
# Comprobado el 2026-07-20 con una cuenta nueva: Google lista modelos que luego
# rechaza ("no longer available to new users") y tumba otros por demanda
# ("high demand"), así que un único modelo fijo es frágil.
FALLBACK_MODELS = (
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.0-flash-lite",
)

# Recortamos el artículo antes de mandarlo. Los artículos largos (el de
# "Bohemian Rhapsody" pasa de 30.000 caracteres) gastan cuota y hacen la
# respuesta más lenta sin mejorarla: lo que importa casi siempre está al
# principio, que es donde Wikipedia pone la ficha y el origen de la canción.
MAX_CONTEXT_CHARS = 12000

TIMEOUT = 30


INSTRUCCIONES = """\
Eres un asistente que habla de música dentro de la aplicación Wavely.

REGLAS, sin excepción:
1. Responde ÚNICAMENTE con lo que diga el TEXTO DE CONSULTA que te damos. No uses
   nada que sepas por tu cuenta, aunque estés seguro.
2. Si el texto no responde la pregunta, dilo con claridad: "El artículo no dice
   nada sobre eso". No rellenes ni especules.
3. No inventes datos, fechas, cifras, productores ni instrumentos. Si no está
   escrito en el texto, no existe para ti.
4. Responde en español, en tono cercano y breve: dos o tres párrafos como mucho.
5. No repitas estas reglas ni menciones que te dieron un texto; simplemente
   responde.
"""

# Cuando el artículo es del ARTISTA y no de la canción, el modelo tiene que
# saberlo o le atribuirá a la canción cosas que el texto dice del artista.
AVISO_ARTISTA = """\
ATENCIÓN: el texto de consulta es el artículo del ARTISTA, no el de esta canción
concreta. Puedes hablar del artista, su estilo y su trayectoria, pero NO afirmes
cosas sobre esta canción en particular a menos que el texto la mencione por su
nombre. Si te preguntan por la canción y el texto no habla de ella, dilo.
"""


class GeneratorUnavailable(Exception):
    """Ningún modelo respondió. El router lo traduce a 'solo recuperación'."""


def is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


def build_prompt(question: str, context: dict, song: dict) -> str:
    texto = (context.get("text") or "")[:MAX_CONTEXT_CHARS]
    fuente = context.get("source") or {}

    partes = [
        f"CANCIÓN: «{song['name']}» de {song['artist']}.",
        "",
    ]
    if context.get("kind") == "artist":
        partes += [AVISO_ARTISTA, ""]

    partes += [
        f"TEXTO DE CONSULTA (de Wikipedia, artículo «{fuente.get('title', '')}»):",
        '"""',
        texto,
        '"""',
        "",
        f"PREGUNTA DEL USUARIO: {question}",
    ]
    return "\n".join(partes)


async def generate(question: str, context: dict, song: dict) -> dict:
    """
    Devuelve {"answer": str, "model": str}.

    Lanza GeneratorUnavailable si no hay clave o si ningún modelo respondió; el
    router lo convierte en una respuesta útil en vez de un error, porque el
    usuario todavía puede leer la fuente por su cuenta.
    """
    if not is_configured():
        raise GeneratorUnavailable("No hay GEMINI_API_KEY configurada.")

    prompt = build_prompt(question, context, song)

    # El modelo de los ajustes primero, luego los de reserva sin repetir.
    modelos = [settings.GEMINI_MODEL] + [
        m for m in FALLBACK_MODELS if m != settings.GEMINI_MODEL
    ]

    ultimo_error = None
    for modelo in modelos:
        try:
            texto = await _call(modelo, prompt)
        except (httpx.HTTPStatusError, httpx.RequestError, KeyError, IndexError) as exc:
            # Modelo cerrado, sin cuota, caído o respuesta rara: probamos el
            # siguiente en vez de romperle el chat al usuario.
            ultimo_error = exc
            continue

        if texto:
            return {"answer": texto, "model": modelo}

    raise GeneratorUnavailable(f"Ningún modelo respondió ({ultimo_error}).")


async def _call(modelo: str, prompt: str) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": INSTRUCCIONES}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            # Temperatura baja: no queremos creatividad, queremos fidelidad al
            # texto que le dimos.
            "temperature": 0.2,
            "maxOutputTokens": 800,
        },
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            f"{BASE_URL}/{modelo}:generateContent",
            headers={
                "x-goog-api-key": settings.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
        )
    r.raise_for_status()
    data = r.json()

    partes = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in partes).strip()
