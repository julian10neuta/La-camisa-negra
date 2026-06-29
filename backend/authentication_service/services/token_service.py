import httpx
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..repositories.user_repository import UserRepository
from shared.config import settings

class TokenService:
    def __init__(self, db: Session):
        self.db = db
        self.refresh_url = "https://accounts.spotify.com/api/token"

    async def get_valid_spotify_token(self, spotify_id: str) -> str:
        user = UserRepository.get_by_spotify_id(self.db, spotify_id)
        
        if not user:
            raise ValueError(f"Usuario {spotify_id} no encontrado")

        # Si el token no ha expirado, lo devolvemos directo
        if datetime.utcnow() < user.token_expiry:
            return user.access_token

        # Si expiró, pedimos uno nuevo a Spotify
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.refresh_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": user.refresh_token,
                    "client_id": settings.SPOTIFY_CLIENT_ID,
                    "client_secret": settings.SPOTIFY_CLIENT_SECRET,
                }
            )
        
        token_data = response.json()

        if "access_token" not in token_data:
            raise ValueError("Spotify no devolvió un nuevo access_token")

        # Guardamos el nuevo token en BD
        new_expiry = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        UserRepository.update_tokens(
            self.db,
            user,
            access_token=token_data["access_token"],
            token_expiry=new_expiry
        )

        return token_data["access_token"]