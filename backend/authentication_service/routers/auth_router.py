from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from ..services.auth_service import AuthService
from shared.database import get_db
from shared.config import settings
from ..schemas.user_schema import AuthCodeRequest
from ..services.token_service import TokenService

router = APIRouter(tags=["Authentication"])

@router.get("/login-url")
def get_login_url():
    """
    Devuelve la URL de autorización de Spotify en un JSON. 
    El frontend consume este endpoint y redirige al usuario.
    """
    scopes = " ".join([
    "streaming",                  
    "user-read-email",            
    "user-read-private",          
    "user-modify-playback-state", 
    "user-read-playback-state",   
    "user-top-read",              
    "user-read-recently-played",  
    "playlist-modify-public",     
    "playlist-modify-private",
    "playlist-read-private",      # ← agrega este
    "user-library-modify",        
    "user-library-read",
    ])
    
    provider_url = "https://accounts.spotify.com/authorize"
    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": scopes,
        "show_dialog": "true"
    }
    
    return {"url": f"{provider_url}?{urlencode(params)}"}



@router.post("/callback")
async def callback(request: AuthCodeRequest, db: Session = Depends(get_db)):
    # request.code es ahora el dato que viene en el body
    code = request.code
    
    auth_service = AuthService(
        db=db, 
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI
    )
    
    try:
        my_jwt, user = await auth_service.get_user_from_code(code)
        
        if not user.is_premium:
            raise HTTPException(status_code=403, detail="Requiere cuenta Premium")

        return {
            "access_token": my_jwt,
            "token_type": "bearer",
            "user": {"name": user.name, "id": user.id}
        }
    except Exception as e:
        print("ERROR DETALLADO:", str(e))  # ← agrega esta línea
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/tokens/{spotify_id}")
async def get_spotify_token(spotify_id: str, db: Session = Depends(get_db)):
    """
    Endpoint interno — usado por otros microservicios para obtener
    un access_token válido de Spotify para un usuario dado.
    """
    token_service = TokenService(db=db)
    try:
        access_token, token_expiry = await token_service.get_valid_spotify_token(spotify_id)
        # expires_at en ISO 8601 (UTC, naive) — lo consume shared/token_service.py
        # para cachear el token solo por la vida que le queda realmente.
        return {"access_token": access_token, "expires_at": token_expiry.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.post("/logout")
def logout():
    return {"message": "Logout exitoso"}