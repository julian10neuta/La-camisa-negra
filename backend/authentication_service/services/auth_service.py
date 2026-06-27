# authentication_service/services/auth_service.py

import httpx
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..repositories.user_repository import UserRepository
from ..utils.jwt_utils import create_access_token

class AuthService:
    def __init__(self, db: Session, client_id: str, client_secret: str, redirect_uri: str):
        self.db = db
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_url = "https://accounts.spotify.com/api/token"
        self.me_url = "https://api.spotify.com/v1/me"

    async def get_user_from_code(self, code: str):
        # 1. Obtener tokens de Spotify
        async with httpx.AsyncClient() as client:
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            token_resp = await client.post(self.token_url, data=payload)
            token_data = token_resp.json()

            # 2. Obtener perfil de Spotify
            user_resp = await client.get(self.me_url, headers={"Authorization": f"Bearer {token_data['access_token']}"})
            user_info = user_resp.json()

            # 3. Guardar en Postgres vía Repositorio
            user_data = {
                "spotify_id": user_info["id"],
                "name": user_info.get("display_name"),
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                "token_expiry": datetime.utcnow() + timedelta(seconds=token_data["expires_in"]),
                "is_premium": user_info.get("product") == "premium"
            }
            user = UserRepository.create_or_update_user(self.db, user_data)
            
            # 4. Generar tu propio JWT
            my_jwt = create_access_token({"sub": user.spotify_id, "id": user.id})
            
            return my_jwt, user