# authentication_service/repositories/user_repository.py

from sqlalchemy.orm import Session
from sqlalchemy import select
from shared.models import User
from datetime import datetime

class UserRepository:
    
    @staticmethod
    def get_by_spotify_id(db: Session, spotify_id: str) -> User | None:
        """Busca un usuario en la base de datos por su ID de Spotify."""
        statement = select(User).where(User.spotify_id == spotify_id)
        result = db.execute(statement)
        return result.scalars().first()

    @staticmethod
    def create_or_update_user(db: Session, user_data: dict) -> User:
        """
        Si el usuario ya existe, actualiza sus tokens de acceso y refresco.
        Si no existe, lo crea desde cero en Postgres.
        """
        # 1. Intentamos buscar si ya existe
        user = UserRepository.get_by_spotify_id(db, user_data["spotify_id"])
        
        if user:
            # Si existe, actualizamos los datos dinámicos (tokens y plan)
            user.access_token = user_data["access_token"]
            user.refresh_token = user_data["refresh_token"]
            user.token_expiry = user_data["token_expiry"]
            user.is_premium = user_data["is_premium"]
            user.name = user_data.get("name", user.name)  # Por si cambió su display name
        else:
            # Si no existe, instanciamos un nuevo usuario
            user = User(
                spotify_id=user_data["spotify_id"],
                name=user_data.get("name"),
                access_token=user_data["access_token"],
                refresh_token=user_data["refresh_token"],
                token_expiry=user_data["token_expiry"],
                is_premium=user_data["is_premium"],
                registration_date=datetime.utcnow()
            )
            db.add(user)
        
        # 2. Guardamos los cambios de verdad en Postgres
        db.commit()
        db.refresh(user)
        return user