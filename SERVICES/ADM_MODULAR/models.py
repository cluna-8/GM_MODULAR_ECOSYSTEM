from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Float,
    Boolean,
)
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    role = Column(String)  # admin, user, monitor
    is_active = Column(Boolean, default=True)


class Token(Base):
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)  # El token hcg_...
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)  # Nombre descriptivo del token
    total_tokens_consumed = Column(Integer, default=0)  # Contador de uso GPT
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class APILog(Base):
    __tablename__ = "api_logs"
    id = Column(Integer, primary_key=True, index=True)
    token_id = Column(Integer, ForeignKey("tokens.id"))
    endpoint = Column(String)  # A qué chat se llamó (chat1, chat2, etc)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    # Campos de auditoría profesional
    auditor_alert = Column(Boolean, default=False)   # True si el auditor marcó riesgo
    session_id = Column(String, nullable=True)        # Para acceder a la traza completa
    prompt_snippet = Column(Text, nullable=True)      # Primeros 200 chars del prompt
