from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Infraestructura
    DATABASE_URL: str = "postgresql://admin:secretpassword@localhost:5432/la_camisa_negra"

    # Redis
    REDIS_HOST: str = "redis_cache"
    REDIS_PORT: int = 6379

    # Spotify
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    SPOTIFY_REDIRECT_URI: str = ""

    # Auth
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Chroma
    CHROMA_HOST: str = "chroma_db"
    CHROMA_PORT: int = 8000

    # General
    ENV: str = "development"

    class Config:
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        extra = "ignore"


settings = Settings()