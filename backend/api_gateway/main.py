from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import httpx

from .security import is_public_path, extract_spotify_id_from_request

app = FastAPI(title="API Gateway - La Camisa Negra")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICES = {
    "auth":  "http://authentication_service:8001",
    "music": "http://music_service:8002",
    "dashboard": "http://dashboard_service:8005",
    "recommendation": "http://recommendation_service:8004",
    "rag": "http://rag_service:8006",
}


async def proxy_request(target_url: str, request: Request, extra_headers: dict = {}) -> Response:
    """
    Función central de proxy. Reenvía la request al microservicio
    destino e inyecta headers adicionales si se pasan.
    """
    method = request.method
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.update(extra_headers)  # aquí inyectamos X-Spotify-ID y similares

    query_params = dict(request.query_params)
    body = await request.body()

    # Timeout amplio: generar recomendaciones hace decenas de llamadas a Deezer +
    # Spotify y puede tardar ~15-30s. El default de httpx (5s) cortaba con 503.
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.request(
                method=method,
                url=target_url,
                headers=headers,
                params=query_params,
                content=body,
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Servicio no disponible: {exc}")

    # Filtramos set-cookie para manejarlo manualmente si hace falta
    headers_to_forward = {
        k: v for k, v in response.headers.items()
        if k.lower() != "set-cookie"
    }

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=headers_to_forward,
    )


# ─── Rutas públicas: auth ────────────────────────────────────────────────────

@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_auth(path: str, request: Request):
    """
    Rutas de autenticación — no requieren JWT.
    El login y callback de Spotify van aquí.
    """
    target_url = f"{SERVICES['auth']}/auth/{path}"
    return await proxy_request(target_url, request)


# ─── Rutas protegidas: music ─────────────────────────────────────────────────

@app.api_route("/music/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_music(path: str, request: Request):
    """
    Rutas del music_service — requieren JWT válido.
    El gateway valida el token e inyecta X-Spotify-ID para que
    el music_service no necesite conocer SECRET_KEY.
    """
    spotify_id = extract_spotify_id_from_request(request)

    target_url = f"{SERVICES['music']}/music/{path}"

    return await proxy_request(
        target_url,
        request,
        extra_headers={"X-Spotify-ID": spotify_id},
    )


# ─── Rutas protegidas: dashboard ─────────────────────────────────────────────

@app.api_route("/dashboard{path:path}", methods=["GET"])
async def proxy_dashboard(path: str, request: Request):
    """
    Rutas del dashboard_service — requieren JWT válido.

    Nota sobre el patrón de la ruta: es "/dashboard{path:path}" y no
    "/dashboard/{path:path}" como las demás, porque este servicio expone la raíz
    ("/dashboard", sin nada detrás). Con la barra obligatoria, GET /dashboard no
    casaría con nada y daría 404.

    Solo GET: este servicio no escribe nada, solo lee y compone.
    """
    spotify_id = extract_spotify_id_from_request(request)

    target_url = f"{SERVICES['dashboard']}/dashboard{path}"

    return await proxy_request(
        target_url,
        request,
        extra_headers={"X-Spotify-ID": spotify_id},
    )


# ─── Rutas protegidas: recommendation ────────────────────────────────────────

@app.api_route("/recommendations/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_recommendation(path: str, request: Request):
    """
    Rutas del recommendation_service — requieren JWT válido.
    Igual que music: el gateway valida el token e inyecta X-Spotify-ID.
    """
    spotify_id = extract_spotify_id_from_request(request)

    target_url = f"{SERVICES['recommendation']}/recommendations/{path}"

    return await proxy_request(
        target_url,
        request,
        extra_headers={"X-Spotify-ID": spotify_id},
    )


# ─── Rutas protegidas: rag ───────────────────────────────────────────────────

@app.api_route("/rag/{path:path}", methods=["GET", "POST"])
async def proxy_rag(path: str, request: Request):
    """
    Rutas del rag_service (chat sobre canciones) — requieren JWT válido.
    Mismo patrón que music: el gateway valida el token e inyecta X-Spotify-ID.
    """
    spotify_id = extract_spotify_id_from_request(request)

    target_url = f"{SERVICES['rag']}/rag/{path}"

    return await proxy_request(
        target_url,
        request,
        extra_headers={"X-Spotify-ID": spotify_id},
    )