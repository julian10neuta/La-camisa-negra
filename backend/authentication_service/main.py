import os
from fastapi import FastAPI, HTTPException, Query, Cookie
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import httpx

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

ENV = os.getenv("ENV", "development")
IS_PRODUCTION = ENV == "production"

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise ValueError("Missing Spotify API credentials in environment variables.")

app = FastAPI(title="La Camisa Negra proyect")

#The middleware are used to verify the requests before they reach the endpoints.
app.add_middleware(
    #CORS (Cross-Origin Resource Sharing) middleware allows the server to specify who can access its resources and how they can be accessed. This is important for security and for enabling cross-origin requests from web applications.
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

SPOTIFY_AUTH_URL  = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL    = "https://api.spotify.com/v1/me"

@app.get("/login")
def login():

    # The scopes define the permissions that the application is requesting from the user. Each scope corresponds to a specific action or access level in the Spotify API. By specifying these scopes, the application can request access to certain features of the user's Spotify account, such as modifying playback state, reading playback state, accessing top tracks and artists, and reading recently played tracks.
    #Is possible that we need to add more 
    scopes = " ".join([
        "streaming",                  # Web Playback SDK
        "user-read-email",            # Ver email del usuario
        "user-read-private",          # Ver si es premium
        "user-modify-playback-state", # Play/pause/skip
        "user-read-playback-state",   # Ver estado actual
        "user-top-read",              # Top artistas/canciones
        "user-read-recently-played",  # Historial reciente
        "playlist-modify-public",     # Crear/editar playlists
        "playlist-modify-private",
        "user-library-modify",        # Favoritos
        "user-library-read",
    ])

    url = (
        f"{SPOTIFY_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&scope={scopes}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(url=url)



@app.get("/callback")
async def callback(code:str=Query(None), error:str=Query(None)):
    if error:
        return RedirectResponse(url="http://localhost:5173?error=access_denied")
    
    if not code:
        raise HTTPException(status_code=400, detail="No hay código de autorización")
    
    async with httpx.AsyncClient() as client:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }

        headers={"Content-Type": "application/x-www-form-urlencoded"}

        token_response = await client.post(
            SPOTIFY_TOKEN_URL,   # ← URL correcta
            data=payload,
            headers=headers
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=token_response.status_code, detail="Error al obtener el token de acceso")
        
        tokens=token_response.json()
        access_token=tokens.get("access_token")
        refresh_token=tokens.get("refresh_token")

        user_response = await client.get(
            SPOTIFY_ME_URL,      # ← URL correcta
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if user_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error al obtener datos del usuario")        

        user_data    = user_response.json()
        product_type = user_data.get("product")  # "premium" o "free"
        spotify_id   = user_data.get("id")
        display_name = user_data.get("display_name")

        if product_type != "premium":
            return RedirectResponse(url="http://localhost:5173?error=premium_required")

        response = RedirectResponse(url="http://localhost:5173/dashboard")

        response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=False,
        secure=IS_PRODUCTION,        # False en local, True en producción
        samesite="none" if IS_PRODUCTION else "lax",
        max_age=3600
    )

        # refresh_token: httponly=True, JavaScript nunca lo toca
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=IS_PRODUCTION,        # False en local, True en producción
            samesite="none" if IS_PRODUCTION else "lax",
            max_age=60 * 60 * 24 * 30
        )

        return response


@app.get("/test-cookies")
def test_cookies(access_token: str = Cookie(None), refresh_token: str = Cookie(None)):
    """
    Endpoint de prueba para verificar si el backend recibe las cookies.
    """
    if not access_token:
        return {"status": "error", "message": "No se encontró la cookie access_token"}
        
    return {
        "status": "success",
        "message": "¡El backend leyó las cookies perfectamente!",
        "tokens_detectados": {
            "access_token_recortado": f"{access_token[:10]}...", # Solo mostramos el inicio por seguridad
            "refresh_token_detectado": refresh_token is not None
        }
    }