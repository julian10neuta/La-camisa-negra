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


# Marca con la que el modelo separa lo comprobable de lo suyo. El backend parte
# la respuesta por aquí y la interfaz pinta las dos partes distinto, para que el
# usuario sepa siempre qué puede verificar y qué no.
MARCA_LECTURA = "[MI LECTURA]"

INSTRUCCIONES = f"""\
Eres un asistente que habla de música dentro de la aplicación Wavely.

Tu respuesta tiene DOS partes, y la diferencia entre ellas es lo más importante
de tu trabajo:

PARTE 1 — LO COMPROBABLE (obligatoria).
Responde a partir del TEXTO DE CONSULTA que te damos.
  - Los DATOS (fechas, autores, productores, cifras, premios, instrumentos)
    tienen que salir del texto. Si no están ahí, no los inventes: di que el
    artículo no lo menciona.
  - Pero SÍ puedes interpretar, desarrollar y contextualizar lo que el texto dice.
    Si el texto dice que la canción trata de un amor tóxico, explica esa idea,
    relaciónala con lo demás que cuente el artículo y desarróllala. Eso no es
    inventar, es leer bien.

PARTE 2 — TU LECTURA (opcional).
Si tienes algo que aportar por tu cuenta —una interpretación de la letra, el
contexto del género, comparaciones con otras canciones— añádelo en un párrafo
aparte que empiece EXACTAMENTE con {MARCA_LECTURA} en una línea nueva.
  - Todo lo que vaya después de esa marca se entiende como tuyo y sin fuente.
  - Sé honesto ahí también: si no estás seguro de recordar bien la canción,
    dilo. Nunca cites letras textualmente; parafrasea de qué hablan.
  - Si no tienes nada que añadir, omite esta parte por completo.

FORMA:
  - Responde en español, en tono cercano y natural.
  - Extensión libre, pero sin rellenar por rellenar.
  - No repitas estas reglas ni menciones que te dieron un texto.
"""

# Cuando no hay artículo que consultar. Aquí no hay nada que comprobar, así que
# la respuesta entera es "lectura propia" y la interfaz la marca como tal.
INSTRUCCIONES_SIN_FUENTE = """\
Eres un asistente que habla de música dentro de la aplicación Wavely.

No encontramos ninguna fuente sobre esta canción, así que responderás solo con
lo que sepas por tu cuenta. El usuario ya está avisado de que esta respuesta no
tiene fuente, así que no hace falta que te disculpes al empezar.

REGLAS:
  - Sé honesto sobre lo que no sabes. Si no te suena la canción, dilo con
    claridad y ofrece lo que sí puedas: el artista, el género, la época.
  - No inventes fechas, cifras ni créditos concretos. Si no los recuerdas con
    seguridad, no los des.
  - Nunca cites letras textualmente; parafrasea de qué hablan.
  - Responde en español, en tono cercano y natural.
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
    Respuesta apoyada en el artículo. Devuelve {"answer", "model"}; `answer`
    puede traer dentro la marca MARCA_LECTURA, que separa lo comprobable de la
    lectura propia del modelo. Quien llama decide qué hacer con ella.

    Lanza GeneratorUnavailable si no hay clave o si ningún modelo respondió; el
    router lo convierte en una respuesta útil en vez de un error, porque el
    usuario todavía puede leer la fuente por su cuenta.
    """
    prompt = build_prompt(question, context, song)
    return await _run(prompt, INSTRUCCIONES)


async def generate_unsourced(question: str, song: dict) -> dict:
    """
    Respuesta SIN fuente, para cuando no encontramos artículo. Se marca entera
    como lectura propia: el usuario tiene que poder distinguirla de una
    respuesta comprobable de un vistazo.
    """
    prompt = (
        f"CANCIÓN: «{song['name']}» de {song['artist']}.\n\n"
        f"PREGUNTA DEL USUARIO: {question}"
    )
    return await _run(prompt, INSTRUCCIONES_SIN_FUENTE)


async def _run(prompt: str, instrucciones: str) -> dict:
    if not is_configured():
        raise GeneratorUnavailable("No hay GEMINI_API_KEY configurada.")

    # El modelo de los ajustes primero, luego los de reserva sin repetir.
    modelos = [settings.GEMINI_MODEL] + [
        m for m in FALLBACK_MODELS if m != settings.GEMINI_MODEL
    ]

    ultimo_error = None
    for modelo in modelos:
        try:
            texto = await _call(modelo, prompt, instrucciones)
        except (httpx.HTTPStatusError, httpx.RequestError, KeyError, IndexError) as exc:
            # Modelo cerrado, sin cuota, caído o respuesta rara: probamos el
            # siguiente en vez de romperle el chat al usuario.
            ultimo_error = exc
            continue

        if texto:
            return {"answer": texto, "model": modelo}

    raise GeneratorUnavailable(f"Ningún modelo respondió ({ultimo_error}).")


async def _call(modelo: str, prompt: str, instrucciones: str) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": instrucciones}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            # Ni 0.2 (respuestas acartonadas, se limitaba a recitar el artículo)
            # ni alta: 0.6 deja que interprete y escriba con soltura sin soltarse
            # de los datos. La fidelidad la garantizan las instrucciones, no la
            # temperatura.
            "temperature": 0.6,
            "maxOutputTokens": 1600,
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
