# authentication_service/utils/jwt_utils.py
import jwt
from datetime import datetime, timedelta, timezone
# Importamos la clase settings que ya configuramos con Pydantic
from shared.config import settings 

def create_access_token(data: dict):
    to_encode = data.copy()
    
    # Usamos settings para obtener el tiempo de vida (o lo definimos fijo)
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    
    # Usamos settings.SECRET_KEY y settings.ALGORITHM
    return jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )