# authentication_service/services/auth_service.py

import httpx
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
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
        # Todo se ejecuta de forma secuencial dentro del bloque AsyncClient
        async with httpx.AsyncClient() as client:
            # 1. Obtener tokens de Spotify
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            token_resp = await client.post(self.token_url, data=payload)
            # El endpoint de token devuelve JSON tanto en éxito como en error.
            try:
                token_data = token_resp.json()
            except ValueError:
                token_data = {}
            print("Respuesta de Spotify:", token_data)
            if token_resp.status_code != 200 or "access_token" not in token_data:
                # p. ej. code inválido o ya usado (invalid_grant).
                detail = (
                    token_data.get("error_description")
                    or token_data.get("error")
                    or "no se pudo intercambiar el code por un token"
                )
                raise HTTPException(status_code=400, detail=f"Spotify: {detail}")

            # 2. Obtener perfil de Spotify
            user_resp = await client.get(
                self.me_url,
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )
            # No asumimos que /me devuelva JSON: con 429 responde texto plano
            # ("Too many requests") y hacer .json() ahí reventaba con un 400
            # incomprensible. Verificamos el status y damos un error legible.
            if user_resp.status_code == 429:
                retry = user_resp.headers.get("Retry-After", "?")
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Spotify limitó la app por exceso de peticiones; "
                        f"reintenta en ~{retry}s (o usa otro client_id)."
                    ),
                )
            if user_resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Spotify /me devolvió {user_resp.status_code}",
                )
            user_info = user_resp.json()
            print("Info usuario:", user_info)

            # 3. Guardar en Postgres vía Repositorio
            user_data = {
                "spotify_id": user_info["id"],
                "name": user_info.get("display_name"),
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                # Usamos timezone.utc para evitar el aviso de obsolescencia de utcnow
                "token_expiry": datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"]),
                "is_premium": user_info.get("product") == "premium"
            }
            user = UserRepository.create_or_update_user(self.db, user_data)
            
            # 4. Generar tu propio JWT
            my_jwt = create_access_token({"sub": user.spotify_id, "id": user.id})
            
            return my_jwt, user
