# dashboard_service/services/composer.py
# ----------------------------------------------------------------------------
# El corazón del dashboard_service, y lo más importante que hay que entender de
# él: AQUÍ NO HAY LÓGICA DE NEGOCIO NI ACCESO A DATOS.
#
# Este servicio no tiene base de datos, ni repositorios, ni sabe qué es un
# "play". Lo único que hace es llamar a los servicios que SÍ lo saben y juntar
# sus respuestas en una sola. Es el patrón **API Composition** (Richardson,
# "Microservices Patterns"): cuando una pantalla necesita datos de varios
# servicios, alguien tiene que juntarlos; hacerlo aquí evita que el navegador
# haga tres viajes y que el frontend tenga que saber qué servicio guarda qué.
#
# Si algún día alguien siente la tentación de meter aquí una consulta SQL: eso
# sería duplicar la lógica de music_service y tener dos servicios escribiendo
# sobre las mismas tablas. Las consultas van en su dueño; aquí solo se compone.
# ----------------------------------------------------------------------------

import asyncio

import httpx

MUSIC_URL = "http://music_service:8002"
RECOMMENDATION_URL = "http://recommendation_service:8004"

# Un dashboard son cuatro llamadas internas, todas contra servicios de nuestra
# propia red: si una tarda más que esto, algo va mal y es mejor enseñar la
# pantalla incompleta que dejar al usuario mirando un spinner.
TIMEOUT_SEGUNDOS = 10.0


async def _get(client: httpx.AsyncClient, url: str, spotify_id: str, params: dict) -> dict | None:
    """
    Una llamada a un servicio de dentro. Devuelve None si falla, en vez de
    lanzar: el dashboard tiene cuatro secciones y que una se caiga no debe
    tumbar las otras tres. Quien llama decide qué enseñar en su lugar.

    La identidad se reenvía con la cabecera X-Spotify-ID, que es el contrato de
    la casa: el gateway la valida y la inyecta, y los servicios de dentro
    confían en ella (ver api_gateway/main.py). Este servicio hace lo mismo que el
    gateway al hablar hacia dentro.
    """
    try:
        r = await client.get(url, params=params, headers={"X-Spotify-ID": spotify_id})
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


async def compose_dashboard(spotify_id: str, days: int, top: int, period: str, limit: int) -> dict:
    """
    Arma la pantalla del Dashboard en una sola respuesta.

    Las cuatro llamadas van EN PARALELO (asyncio.gather), no en fila: son
    independientes entre sí, y en serie el usuario esperaría la suma de las
    cuatro en vez de la más lenta.

    Sobre las dos "ventanas" que conviven aquí, que es la parte confusa:
      - `days` (24h / 7d) es la ventana de las ESTADÍSTICAS. La pide el diseño.
      - `period` (semanal / mensual) es el de las RECOMENDACIONES, y sale de los
        Ajustes del usuario.
    Son cosas distintas y NO se mezclan a propósito: mirar tus estadísticas de
    hoy no debería cambiar qué recomendaciones tienes. El CRC del diseño dice
    "las 15 recomendaciones de la ventana activa", pero el motor nunca tuvo
    ventanas de 24h — decisión del dueño (2026-07-14): la ventana solo afecta a
    las estadísticas.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
        top_data, stats, recs = await asyncio.gather(
            _get(client, f"{MUSIC_URL}/music/interactions/top", spotify_id,
                 {"days": days, "limit": top}),
            _get(client, f"{MUSIC_URL}/music/interactions/stats", spotify_id,
                 {"days": days}),
            _get(client, f"{RECOMMENDATION_URL}/recommendations/list", spotify_id,
                 {"period": period, "limit": limit}),
        )

    return {
        "window": {"days": days, "since": (top_data or {}).get("since")},
        "top": {
            "songs": (top_data or {}).get("songs", []),
            "artists": (top_data or {}).get("artists", []),
            "albums": (top_data or {}).get("albums", []),
        },
        "stats": stats,          # None si music_service falló
        "recommendations": recs, # None si recommendation_service falló
        # Qué partes vinieron mal, para que el frontend pueda decirlo en vez de
        # pintar ceros como si fueran datos de verdad. Un cero inventado miente;
        # un "no se pudo cargar" no.
        "failed": [
            name for name, value in
            (("top", top_data), ("stats", stats), ("recommendations", recs))
            if value is None
        ],
    }
