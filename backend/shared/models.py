from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    spotify_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_expiry = Column(DateTime, nullable=False)
    is_premium = Column(Boolean, default=False)
    registration_date = Column(DateTime, default=func.now())