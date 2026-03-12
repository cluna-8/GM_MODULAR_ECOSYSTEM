# auth.py - Authentication and Token Management
from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import secrets
import uuid
import logging

from database import get_db
from models import User, Token, UserRole, TokenStatus

logger = logging.getLogger(__name__)

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = "your-super-secret-key-change-in-production"  # TODO: Load from env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Bearer token security
security = HTTPBearer()

# ============================================================================
# PASSWORD UTILITIES
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

# ============================================================================
# JWT TOKEN UTILITIES
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token for admin authentication"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str) -> Optional[dict]:
    """Verify JWT access token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return {"username": username}
    except JWTError:
        return None

# ============================================================================
# API TOKEN UTILITIES
# ============================================================================

def generate_api_token() -> str:
    """Generate a secure API token"""
    # Format: hcg_[32 random characters]
    random_part = secrets.token_urlsafe(24)  # ~32 chars when base64 encoded
    return f"hcg_{random_part}"

def create_api_token(db: Session, user_id: int, name: str, created_by_id: int) -> Token:
    """Create a new API token for a user"""
    try:
        # Generate unique token
        token_string = generate_api_token()
        
        # Ensure token is unique
        while db.query(Token).filter(Token.token == token_string).first():
            token_string = generate_api_token()
        
        # Create token record
        db_token = Token(
            token=token_string,
            user_id=user_id,
            name=name,
            status=TokenStatus.ACTIVE.value,
            created_at=datetime.utcnow()
        )
        
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        
        logger.info(f"✅ API token created for user_id={user_id}, name='{name}'")
        return db_token
        
    except Exception as e:
        logger.error(f"❌ Error creating API token: {e}")
        db.rollback()
        raise

def verify_api_token(db: Session, token: str) -> Optional[Token]:
    """Verify and return API token if valid"""
    try:
        db_token = db.query(Token).filter(
            Token.token == token,
            Token.status == TokenStatus.ACTIVE.value
        ).join(User, Token.user_id == User.id).filter(User.is_active == True).first()
        
        if db_token:
            # Update last used timestamp
            db_token.last_used_at = datetime.utcnow()
            db.commit()
            
        return db_token
        
    except Exception as e:
        logger.error(f"❌ Error verifying API token: {e}")
        return None

def revoke_api_token(db: Session, token_id: int, revoked_by_id: int) -> bool:
    """Revoke an API token"""
    try:
        db_token = db.query(Token).filter(Token.id == token_id).first()
        
        if not db_token:
            return False
        
        db_token.status = TokenStatus.REVOKED.value
        db_token.revoked_at = datetime.utcnow()
        db_token.revoked_by = revoked_by_id
        
        db.commit()
        
        logger.info(f"✅ API token revoked: token_id={token_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error revoking API token: {e}")
        db.rollback()
        return False

# ============================================================================
# USER AUTHENTICATION
# ============================================================================

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password"""
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not user.is_active:
        return None
    
    # For now, we'll use a simple password check
    # In production, you'd store hashed passwords
    if password == "admin123":  # TODO: Implement proper password hashing
        return user
    
    return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), 
                    db: Session = Depends(get_db)) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = verify_access_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        username = payload.get("username")
        if username is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    
    return user

def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure current user is an admin"""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

def get_current_monitor_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure current user is monitor or admin"""
    if current_user.role not in [UserRole.ADMIN.value, UserRole.MONITOR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Monitor or Admin privileges required"
        )
    return current_user

# ============================================================================
# API TOKEN DEPENDENCIES
# ============================================================================

def get_api_token_from_header(credentials: HTTPAuthorizationCredentials = Depends(security),
                             db: Session = Depends(get_db)) -> Token:
    """Get and verify API token from Authorization header"""
    token_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired API token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify token format
    token = credentials.credentials
    if not token.startswith("hcg_"):
        raise token_exception
    
    # Verify token in database
    db_token = verify_api_token(db, token)
    if not db_token:
        raise token_exception
    
    return db_token

def require_user_token(db_token: Token = Depends(get_api_token_from_header)) -> Token:
    """Require token with USER role (for medical API access)"""
    if db_token.user.role != UserRole.USER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User token required for this endpoint"
        )
    return db_token

# ============================================================================
# USER MANAGEMENT
# ============================================================================

def create_user(db: Session, username: str, email: str, role: UserRole, 
               created_by_id: int, password: str = None) -> User:
    """Create a new user"""
    try:
        # Check if username or email already exists
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            raise ValueError("Username or email already exists")
        
        # Create new user
        db_user = User(
            username=username,
            email=email,
            role=role.value,
            created_by=created_by_id,
            created_at=datetime.utcnow()
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"✅ User created: {username} ({role.value})")
        return db_user
        
    except Exception as e:
        logger.error(f"❌ Error creating user: {e}")
        db.rollback()
        raise

def deactivate_user(db: Session, user_id: int) -> bool:
    """Deactivate a user and revoke all their tokens"""
    try:
        # Deactivate user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        user.is_active = False
        
        # Revoke all active tokens
        active_tokens = db.query(Token).filter(
            Token.user_id == user_id,
            Token.status == TokenStatus.ACTIVE.value
        ).all()
        
        for token in active_tokens:
            token.status = TokenStatus.REVOKED.value
            token.revoked_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"✅ User deactivated: user_id={user_id}, tokens_revoked={len(active_tokens)}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error deactivating user: {e}")
        db.rollback()
        return False

# ============================================================================
# TOKEN USAGE TRACKING
# ============================================================================

def update_token_usage(db: Session, token_id: int, tokens_consumed: int = 0) -> bool:
    """Update token usage statistics"""
    try:
        db_token = db.query(Token).filter(Token.id == token_id).first()
        if not db_token:
            return False
        
        db_token.total_requests += 1
        db_token.total_tokens_consumed += tokens_consumed
        db_token.last_used_at = datetime.utcnow()
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating token usage: {e}")
        db.rollback()
        return False

# ============================================================================
# UTILITIES
# ============================================================================

def get_user_permissions(user: User) -> dict:
    """Get user permissions based on role"""
    base_permissions = {
        "can_use_medical_api": False,
        "can_view_own_sessions": False,
        "can_view_all_sessions": False,
        "can_manage_tokens": False,
        "can_manage_users": False,
        "can_view_statistics": False
    }
    
    if user.role == UserRole.USER.value:
        base_permissions.update({
            "can_use_medical_api": True,
            "can_view_own_sessions": True
        })
    elif user.role == UserRole.MONITOR.value:
        base_permissions.update({
            "can_view_all_sessions": True,
            "can_view_statistics": True
        })
    elif user.role == UserRole.ADMIN.value:
        # Admin can do everything
        for key in base_permissions:
            base_permissions[key] = True
    
    return base_permissions