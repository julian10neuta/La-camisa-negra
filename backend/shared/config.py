from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Infraestructura
    DATABASE_URL: str = "postgresql://admin:secretpassword@localhost:5432/la_camisa_negra"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Spotify (Las agregamos porque las vas a necesitar pronto)
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    SPOTIFY_REDIRECT_URI: str = ""
    
    # Otras variables
    ENV: str = "development"
    OPENAI_API_KEY: str = ""
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8003

    class Config:
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        extra = "ignore"  # <-- ESTA ES LA LÍNEA MÁGICA QUE SOLUCIONA EL ERROR

settings = Settings()