from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from ..services.auth_service import AuthService
from shared.database import get_db
from shared.config import settings
from ..schemas.user_schema import AuthCodeRequest

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
        "user-library-modify",        
        "user-library-read",
    ])
    
    provider_url = "https://accounts.spotify.com/authorize"
    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": scopes,
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
        raise HTTPException(status_code=400, detail=str(e))