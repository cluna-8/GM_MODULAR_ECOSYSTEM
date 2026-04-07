# models.py - Database Models for API Gateway (FIXED)
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

Base = declarative_base()

# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user" 
    MONITOR = "monitor"

class TokenStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"

# ============================================================================
# DATABASE MODELS (SQLAlchemy)
# ============================================================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.USER.value)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships - Fixed with explicit foreign_keys
    tokens = relationship("Token", back_populates="user", foreign_keys="Token.user_id")
    created_users = relationship("User", remote_side=[id])

class Token(Base):
    __tablename__ = "tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)  # Token description/name
    status = Column(String(20), nullable=False, default=TokenStatus.ACTIVE.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Usage tracking
    total_requests = Column(Integer, default=0)
    total_tokens_consumed = Column(Integer, default=0)
    
    # Relationships - Fixed with explicit foreign_keys
    user = relationship("User", back_populates="tokens", foreign_keys=[user_id])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by])
    sessions = relationship("Session", back_populates="token")
    requests = relationship("APIRequest", back_populates="token")

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    token_id = Column(Integer, ForeignKey("tokens.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Session metadata
    total_messages = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)
    tools_used = Column(Text, nullable=True)  # JSON string
    prompt_modes_used = Column(Text, nullable=True)  # JSON string
    language_detected = Column(String(10), nullable=True)
    
    # Relationships
    token = relationship("Token", back_populates="sessions")
    requests = relationship("APIRequest", back_populates="session")

class APIRequest(Base):
    __tablename__ = "api_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    token_id = Column(Integer, ForeignKey("tokens.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    endpoint = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)
    
    # Request details
    request_data = Column(Text, nullable=True)  # JSON string
    response_status = Column(Integer, nullable=False)
    response_data = Column(Text, nullable=True)  # JSON string
    
    # Token usage
    tokens_consumed = Column(Integer, default=0)
    processing_time = Column(Float, nullable=True)  # seconds
    
    # Cost estimation
    estimated_cost_usd = Column(Float, default=0.0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)


    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Tool information
    tool_used = Column(String(50), nullable=True)
    prompt_mode = Column(String(50), nullable=True)
    language_detected = Column(String(10), nullable=True)
    
    # Relationships
    token = relationship("Token", back_populates="requests")
    session = relationship("Session", back_populates="requests") 

# ============================================================================
# PYDANTIC MODELS (API Schemas)
# ============================================================================

# User schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    role: UserRole = UserRole.USER

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Token schemas
class TokenCreate(BaseModel):
    user_id: int
    name: str = Field(..., min_length=3, max_length=100)

class TokenResponse(BaseModel):
    id: int
    token: str
    name: str
    status: TokenStatus
    created_at: datetime
    last_used_at: Optional[datetime] = None
    total_requests: int = 0
    total_tokens_consumed: int = 0
    user: UserResponse
    
    class Config:
        from_attributes = True

# Session schemas
class SessionResponse(BaseModel):
    id: int
    session_id: str
    created_at: datetime
    last_activity: datetime
    is_active: bool
    total_messages: int = 0
    total_tokens_used: int = 0
    tools_used: Optional[List[str]] = None
    prompt_modes_used: Optional[List[str]] = None
    language_detected: Optional[str] = None
    
    class Config:
        from_attributes = True

# API Request schemas
class APIRequestResponse(BaseModel):
    id: int
    endpoint: str
    method: str
    response_status: int
    tokens_consumed: int = 0
    processing_time: Optional[float] = None
    created_at: datetime
    tool_used: Optional[str] = None
    prompt_mode: Optional[str] = None
    language_detected: Optional[str] = None
    
    class Config:
        from_attributes = True

# Medical API request schemas
class MedicalChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session: Optional[str] = None
    tools: Optional[str] = None
    prompt_mode: Optional[str] = "medical"
    language: Optional[str] = "auto"

class MedicalToolRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session: Optional[str] = None
    max_results: Optional[int] = Field(3, ge=1, le=10)
    format_response: Optional[bool] = True
    language: Optional[str] = "auto"

# Statistics schemas
class UserStats(BaseModel):
    total_tokens: int
    total_requests: int
    active_sessions: int
    last_activity: Optional[datetime] = None

class SystemStats(BaseModel):
    total_users: int
    active_tokens: int
    total_sessions: int
    total_requests: int
    total_tokens_consumed: int
    top_tools_used: List[dict]
    requests_last_24h: int

# Authentication schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse