# main.py - Healthcare API Gateway
from fastapi import FastAPI, HTTPException, Depends, status, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
import httpx
import json
import time
import logging
import os
from datetime import datetime, timedelta

# Local imports
from database import get_db, init_database, database_health_check
from models import (
    User, Token, Session as DBSession, APIRequest, UserRole, TokenStatus,
    UserCreate, UserResponse, TokenCreate, TokenResponse, SessionResponse,
    APIRequestResponse, UserStats, SystemStats, LoginRequest, LoginResponse,
    MedicalChatRequest, MedicalToolRequest
)
from auth import (
    authenticate_user, create_access_token, get_current_admin_user,
    get_current_monitor_or_admin, create_api_token, verify_api_token,
    revoke_api_token, create_user, deactivate_user, update_token_usage,
    get_api_token_from_header, require_user_token, get_user_permissions
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Healthcare API Gateway",
    description="API Gateway for Healthcare Chatbot with authentication, token management, and usage tracking",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MEDICAL_API_URL = os.getenv("MEDICAL_API_URL", "http://healthcare-chat-api:7005")
VOICE_API_URL   = os.getenv("VOICE_API_URL",   "http://gm-voice:7003")
SUMMARY_API_URL = os.getenv("SUMMARY_API_URL", "http://gm-ch-summary:7006")
security = HTTPBearer()

# ============================================================================
# STARTUP AND HEALTH CHECK
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("🚀 Starting Healthcare API Gateway...")
    
    # Only initialize database, don't do any ORM queries
    success = init_database()
    if success:
        from db_init.init_data import setup_database
        setup_database()
        logger.info("✅ API Gateway initialized successfully")
    else:
        logger.error("❌ Failed to initialize database")
        # Don't exit, let the app start anyway

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    # Check database
    db_health = database_health_check()
    
    # Check medical API connectivity
    medical_api_status = "unknown"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MEDICAL_API_URL}/health", timeout=5)
            medical_api_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        medical_api_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_health["status"] == "healthy" and medical_api_status == "healthy" else "degraded",
        "timestamp": datetime.utcnow(),
        "services": {
            "database": db_health,
            "medical_api": {
                "status": medical_api_status,
                "url": MEDICAL_API_URL
            }
        },
        "version": "1.0.0"
    }

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Admin login to get JWT token"""
    user = authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Create JWT token
    access_token = create_access_token(data={"sub": user.username})
    
    return LoginResponse(
        access_token=access_token,
        user=UserResponse.from_orm(user)
    )

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_admin_user)):
    """Get current authenticated user information"""
    return UserResponse.from_orm(current_user)

@app.get("/auth/permissions")
async def get_user_permissions_endpoint(current_user: User = Depends(get_current_admin_user)):
    """Get user permissions"""
    return get_user_permissions(current_user)

# ============================================================================
# USER MANAGEMENT (ADMIN ONLY)
# ============================================================================

@app.post("/admin/users", response_model=UserResponse)
async def create_user_endpoint(
    user_data: UserCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new user (Admin only)"""
    try:
        new_user = create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            role=user_data.role,
            created_by_id=current_user.id,
            password=user_data.password
        )
        return UserResponse.from_orm(new_user)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all users (Admin only)"""
    users = db.query(User).all()
    return [UserResponse.from_orm(user) for user in users]

@app.get("/admin/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get specific user (Admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.from_orm(user)

@app.delete("/admin/users/{user_id}")
async def deactivate_user_endpoint(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Deactivate user and revoke tokens (Admin only)"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    success = deactivate_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deactivated successfully"}

# ============================================================================
# TOKEN MANAGEMENT (ADMIN ONLY)
# ============================================================================

@app.post("/admin/tokens", response_model=TokenResponse)
async def create_token_endpoint(
    token_data: TokenCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new API token (Admin only)"""
    # Verify user exists
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        new_token = create_api_token(db, token_data.user_id, token_data.name, current_user.id)
        return TokenResponse.from_orm(new_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/tokens", response_model=List[TokenResponse])
async def list_tokens(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all tokens (Admin only)"""
    tokens = db.query(Token).join(User).all()
    return [TokenResponse.from_orm(token) for token in tokens]

@app.get("/admin/tokens/{token_id}", response_model=TokenResponse)
async def get_token(
    token_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get specific token (Admin only)"""
    token = db.query(Token).filter(Token.id == token_id).join(User).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return TokenResponse.from_orm(token)

@app.delete("/admin/tokens/{token_id}")
async def revoke_token_endpoint(
    token_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Revoke a token (Admin only)"""
    success = revoke_api_token(db, token_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    
    return {"message": "Token revoked successfully"}

# ============================================================================
# SESSION MONITORING (MONITOR/ADMIN)
# ============================================================================

@app.get("/monitor/sessions", response_model=List[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_monitor_or_admin),
    db: Session = Depends(get_db)
):
    """List all sessions (Monitor/Admin only)"""
    sessions = db.query(DBSession).join(Token).join(User).all()
    
    result = []
    for session in sessions:
        session_data = SessionResponse.from_orm(session)
        
        # Parse JSON fields
        try:
            session_data.tools_used = json.loads(session.tools_used) if session.tools_used else []
        except:
            session_data.tools_used = []
            
        try:
            session_data.prompt_modes_used = json.loads(session.prompt_modes_used) if session.prompt_modes_used else []
        except:
            session_data.prompt_modes_used = []
        
        result.append(session_data)
    
    return result

@app.get("/monitor/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_monitor_or_admin),
    db: Session = Depends(get_db)
):
    """Get specific session details (Monitor/Admin only)"""
    session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = SessionResponse.from_orm(session)
    
    # Parse JSON fields
    try:
        session_data.tools_used = json.loads(session.tools_used) if session.tools_used else []
    except:
        session_data.tools_used = []
        
    try:
        session_data.prompt_modes_used = json.loads(session.prompt_modes_used) if session.prompt_modes_used else []
    except:
        session_data.prompt_modes_used = []
    
    return session_data

@app.get("/monitor/requests", response_model=List[APIRequestResponse])
async def list_requests(
    limit: int = 100,
    current_user: User = Depends(get_current_monitor_or_admin),
    db: Session = Depends(get_db)
):
    """List recent API requests (Monitor/Admin only)"""
    requests = db.query(APIRequest).order_by(APIRequest.created_at.desc()).limit(limit).all()
    return [APIRequestResponse.from_orm(req) for req in requests]

@app.get("/monitor/stats/system", response_model=SystemStats)
async def get_system_stats(
    current_user: User = Depends(get_current_monitor_or_admin),
    db: Session = Depends(get_db)
):
    """Get system-wide statistics (Monitor/Admin only)"""
    
    # Basic counts
    total_users = db.query(User).count()
    active_tokens = db.query(Token).filter(Token.status == TokenStatus.ACTIVE.value).count()
    total_sessions = db.query(DBSession).count()
    total_requests = db.query(APIRequest).count()
    total_tokens_consumed = db.query(APIRequest).with_entities(
        db.func.sum(APIRequest.tokens_consumed)
    ).scalar() or 0
    
    # Requests in last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    requests_24h = db.query(APIRequest).filter(APIRequest.created_at >= yesterday).count()
    
    # Top tools used
    tool_stats = db.query(
        APIRequest.tool_used,
        db.func.count(APIRequest.tool_used).label('count')
    ).filter(
        APIRequest.tool_used.isnot(None)
    ).group_by(APIRequest.tool_used).order_by(db.desc('count')).limit(5).all()
    
    top_tools = [{"tool": tool, "count": count} for tool, count in tool_stats]
    
    return SystemStats(
        total_users=total_users,
        active_tokens=active_tokens,
        total_sessions=total_sessions,
        total_requests=total_requests,
        total_tokens_consumed=total_tokens_consumed,
        top_tools_used=top_tools,
        requests_last_24h=requests_24h
    )

@app.get("/monitor/stats/token/{token_id}", response_model=UserStats)
async def get_token_stats(
    token_id: int,
    current_user: User = Depends(get_current_monitor_or_admin),
    db: Session = Depends(get_db)
):
    """Get statistics for specific token (Monitor/Admin only)"""
    token = db.query(Token).filter(Token.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    active_sessions = db.query(DBSession).filter(
        DBSession.token_id == token_id,
        DBSession.is_active == True
    ).count()
    
    return UserStats(
        total_tokens=token.total_tokens_consumed,
        total_requests=token.total_requests,
        active_sessions=active_sessions,
        last_activity=token.last_used_at
    )

# ============================================================================
# MEDICAL API PROXY ENDPOINTS (USER TOKENS ONLY)
# ============================================================================

#async def log_api_request(db: Session, token_id: int, session_id: Optional[int], 
#                         endpoint: str, method: str, request_data: dict,
#                         response_status: int, response_data: dict,
#                         tokens_consumed: int, processing_time: float,
#                         tool_used: Optional[str], prompt_mode: Optional[str],
#                         language_detected: Optional[str]):
#    """Log API request for tracking"""
#    try:
#        api_request = APIRequest(
#            token_id=token_id,
#            session_id=session_id,
#            endpoint=endpoint,
#            method=method,
#            request_data=json.dumps(request_data),
#            response_status=response_status,
#            response_data=json.dumps(response_data)[:5000],  # Limit size
#            tokens_consumed=tokens_consumed,
#            processing_time=processing_time,
#            tool_used=tool_used,
#            prompt_mode=prompt_mode,
#            language_detected=language_detected,
#            created_at=datetime.utcnow()
#        )
#        
#        db.add(api_request)
#        db.commit()
#        
#        # Update token usage
#        update_token_usage(db, token_id, tokens_consumed)
#        logger.error(f"❌ Error logging API request: {e}")
#        
#    except Exception as e:

##

async def log_api_request(db: Session, token_id: int, session_id: Optional[int], 
                        endpoint: str, method: str, request_data: dict,
                        response_status: int, response_data: dict,
                        tokens_consumed: int, processing_time: float,
                        tool_used: Optional[str], prompt_mode: Optional[str],
                        language_detected: Optional[str],
                        estimated_cost: float = 0.0,  # NUEVO
                        input_tokens: int = 0,        # NUEVO
                        output_tokens: int = 0):      # NUEVO
   """Log API request for tracking"""
   try:
       api_request = APIRequest(
           token_id=token_id,
           session_id=session_id,
           endpoint=endpoint,
           method=method,
           request_data=json.dumps(request_data),
           response_status=response_status,
           response_data=json.dumps(response_data)[:5000],  # Limit size
           tokens_consumed=tokens_consumed,
           processing_time=processing_time,
           tool_used=tool_used,
           prompt_mode=prompt_mode,
           language_detected=language_detected,
           estimated_cost_usd=estimated_cost,    # NUEVO
           input_tokens=input_tokens,            # NUEVO
           output_tokens=output_tokens,          # NUEVO
           created_at=datetime.utcnow()
       )
       
       db.add(api_request)
       db.commit()
       
       # Update token usage
       update_token_usage(db, token_id, tokens_consumed)
       
   except Exception as e:
       logger.error(f"❌ Error logging API request: {e}")

async def get_or_create_session(db: Session, token_id: int, session_id: str) -> DBSession:
    """Get existing session or create new one"""
    session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
    
    if not session:
        session = DBSession(
            session_id=session_id,
            token_id=token_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            is_active=True
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        # Update last activity
        session.last_activity = datetime.utcnow()
        db.commit()
    
    return session





@app.post("/medical/chat")
async def medical_chat_proxy(
    request: MedicalChatRequest,
    db_token: Token = Depends(require_user_token),
    db: Session = Depends(get_db)
):
    """Proxy chat requests to medical API with token validation and logging"""
    start_time = time.time()
    
    try:
        # Generate session if not provided
        if not request.session:
            import uuid
            request.session = f"gw_{uuid.uuid4().hex[:12]}"
        
        # Get or create session in database
        db_session = await get_or_create_session(db, db_token.id, request.session)
        
        # Prepare request for medical API
        medical_request = {
            "message": request.message,
            "session": request.session,
            "tools": request.tools,
            "prompt_mode": request.prompt_mode,
            "language": request.language
        }
        
        # Make request to medical API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MEDICAL_API_URL}/chat",
                json=medical_request,
                timeout=60
            )
            
            response_data = response.json()
            processing_time = time.time() - start_time
            
            # Extract information for logging
            ##################################################################################
            # Count tokens in request and response 
            from token_calculator import analyze_medical_request

            # Analizar tokens y costo
            token_analysis = analyze_medical_request(
                request_data=medical_request,
                response_data=response_data,
                model="gpt-3.5-turbo"  # o el modelo que uses
            )

            tokens_consumed = token_analysis["total_tokens"]
            estimated_cost = 0.0  # Ya no calculamos costo
            ##################################################################################
            tool_used = response_data.get("tool_used")
            prompt_mode = response_data.get("prompt_mode_used")
            language_detected = response_data.get("language_detected")
            
            # Update session statistics
            db_session.total_messages += 1
            db_session.total_tokens_used += tokens_consumed
            
            # Update tools and prompt modes used
            if tool_used:
                try:
                    tools_used = json.loads(db_session.tools_used) if db_session.tools_used else []
                    if tool_used not in tools_used:
                        tools_used.append(tool_used)
                    db_session.tools_used = json.dumps(tools_used)
                except:
                    db_session.tools_used = json.dumps([tool_used])
            
            if prompt_mode:
                try:
                    modes_used = json.loads(db_session.prompt_modes_used) if db_session.prompt_modes_used else []
                    if prompt_mode not in modes_used:
                        modes_used.append(prompt_mode)
                    db_session.prompt_modes_used = json.dumps(modes_used)
                except:
                    db_session.prompt_modes_used = json.dumps([prompt_mode])
            
            if language_detected:
                db_session.language_detected = language_detected
            
            db.commit()
            
            # Log the request
            # Log the request
            await log_api_request(
                db=db,
                token_id=db_token.id,
                session_id=db_session.id,
                endpoint="/medical/chat",
                method="POST",
                request_data=medical_request,
                response_status=response.status_code,
                response_data=response_data,
                tokens_consumed=tokens_consumed,
                processing_time=processing_time,
                tool_used=tool_used,
                prompt_mode=prompt_mode,
                language_detected=language_detected,
                estimated_cost=0.0,                              # Sin costo
                input_tokens=token_analysis["input_tokens"],     
                output_tokens=token_analysis["output_tokens"]
            )
            
            if response.status_code == 200:
                return response_data
            else:
                raise HTTPException(status_code=response.status_code, detail=response_data)
                
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Medical API timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Medical API connection error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Medical chat proxy error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/medical/tools/{tool_name}")
async def medical_tool_proxy(
    tool_name: str,
    request: MedicalToolRequest,
    db_token: Token = Depends(require_user_token),
    db: Session = Depends(get_db)
):
    """Proxy tool requests to medical API with token validation and logging"""
    start_time = time.time()
    
    try:
        # Validate tool name
        valid_tools = ["fda", "pubmed", "clinical-trials", "icd10", "scraping"]
        if tool_name not in valid_tools:
            raise HTTPException(status_code=400, detail=f"Invalid tool. Available: {valid_tools}")
        
        # Prepare request for medical API
        medical_request = {
            "query": request.query,
            "session": request.session,
            "max_results": request.max_results,
            "format_response": request.format_response,
            "language": request.language
        }
        
        # Make request to medical API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MEDICAL_API_URL}/tools/{tool_name}",
                json=medical_request,
                timeout=60
            )
            
            response_data = response.json()
            processing_time = time.time() - start_time
            
            # Extract information for logging
            tokens_consumed = 0  # TODO: Implement token counting
            
            # Get or create session if provided
            db_session_id = None
            if request.session:
                db_session = await get_or_create_session(db, db_token.id, request.session)
                db_session_id = db_session.id
            
            # Log the request
            await log_api_request(
                db=db,
                token_id=db_token.id,
                session_id=db_session_id,
                endpoint=f"/medical/tools/{tool_name}",
                method="POST",
                request_data=medical_request,
                response_status=response.status_code,
                response_data=response_data,
                tokens_consumed=tokens_consumed,
                processing_time=processing_time,
                tool_used=tool_name,
                prompt_mode=None,
                language_detected=request.language
            )
            
            if response.status_code == 200:
                return response_data
            else:
                raise HTTPException(status_code=response.status_code, detail=response_data)
                
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Medical API timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Medical API connection error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Medical tool proxy error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Other medical API endpoints proxy
@app.get("/medical/health")
async def medical_health_proxy(db_token: Token = Depends(require_user_token)):
    """Proxy health check to medical API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MEDICAL_API_URL}/health", timeout=10)
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Medical API unavailable: {str(e)}")

@app.get("/medical/providers")
async def medical_providers_proxy(db_token: Token = Depends(require_user_token)):
    """Proxy providers endpoint to medical API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MEDICAL_API_URL}/providers", timeout=10)
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Medical API unavailable: {str(e)}")

@app.get("/medical/sessions")
async def medical_sessions_proxy(db_token: Token = Depends(require_user_token)):
    """Proxy sessions endpoint to medical API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MEDICAL_API_URL}/sessions", timeout=10)
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Medical API unavailable: {str(e)}")

@app.get("/medical/sessions/{session_id}")
async def medical_session_proxy(
    session_id: str,
    db_token: Token = Depends(require_user_token)
):
    """Proxy specific session endpoint to medical API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MEDICAL_API_URL}/sessions/{session_id}", timeout=10)
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Medical API unavailable: {str(e)}")

@app.delete("/medical/sessions/{session_id}")
async def medical_session_delete_proxy(
    session_id: str,
    db_token: Token = Depends(require_user_token)
):
    """Proxy session deletion to medical API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{MEDICAL_API_URL}/sessions/{session_id}", timeout=10)
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Medical API unavailable: {str(e)}")

# ============================================================================
# USER DASHBOARD ENDPOINTS
# ============================================================================

@app.get("/user/my-sessions", response_model=List[SessionResponse])
async def get_my_sessions(
    db_token: Token = Depends(get_api_token_from_header),
    db: Session = Depends(get_db)
):
    """Get sessions for the current token"""
    sessions = db.query(DBSession).filter(DBSession.token_id == db_token.id).all()
    
    result = []
    for session in sessions:
        session_data = SessionResponse.from_orm(session)
        
        # Parse JSON fields
        try:
            session_data.tools_used = json.loads(session.tools_used) if session.tools_used else []
        except:
            session_data.tools_used = []
            
        try:
            session_data.prompt_modes_used = json.loads(session.prompt_modes_used) if session.prompt_modes_used else []
        except:
            session_data.prompt_modes_used = []
        
        result.append(session_data)
    
    return result

@app.get("/user/my-stats", response_model=UserStats)
async def get_my_stats(
    db_token: Token = Depends(get_api_token_from_header),
    db: Session = Depends(get_db)
):
    """Get statistics for current token"""
    active_sessions = db.query(DBSession).filter(
        DBSession.token_id == db_token.id,
        DBSession.is_active == True
    ).count()
    
    return UserStats(
        total_tokens=db_token.total_tokens_consumed,
        total_requests=db_token.total_requests,
        active_sessions=active_sessions,
        last_activity=db_token.last_used_at
    )

@app.get("/user/my-requests", response_model=List[APIRequestResponse])
async def get_my_requests(
    limit: int = 50,
    db_token: Token = Depends(get_api_token_from_header),
    db: Session = Depends(get_db)
):
    """Get recent requests for current token"""
    requests = db.query(APIRequest).filter(
        APIRequest.token_id == db_token.id
    ).order_by(APIRequest.created_at.desc()).limit(limit).all()
    
    return [APIRequestResponse.from_orm(req) for req in requests]

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@app.get("/info")
async def get_api_info():
    """Get API information"""
    return {
        "name": "Healthcare API Gateway",
        "version": "1.0.0",
        "description": "API Gateway for Healthcare Chatbot with authentication and usage tracking",
        "endpoints": {
            "authentication": ["/auth/login", "/auth/me"],
            "admin": ["/admin/users", "/admin/tokens"],
            "monitoring": ["/monitor/sessions", "/monitor/stats"],
            "medical_api": ["/medical/chat", "/medical/tools/{tool_name}"],
            "user": ["/user/my-sessions", "/user/my-stats"]
        },
        "medical_api_url": MEDICAL_API_URL,
        "documentation": "/docs"
    }

# ============================================================================
# WEBSOCKET ENDPOINT (for real-time chat)
# ============================================================================

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/chat/{token}")
async def websocket_chat(websocket: WebSocket, token: str, db: Session = Depends(get_db)):
    """WebSocket endpoint for real-time chat with token authentication"""
    
    # Verify token
    db_token = verify_api_token(db, token)
    if not db_token or db_token.user.role != UserRole.USER.value:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    await websocket.accept()
    logger.info(f"WebSocket connected for token: {db_token.name}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Validate message format
            if "message" not in message_data:
                await websocket.send_text(json.dumps({
                    "error": "Missing 'message' field"
                }))
                continue
            
            # Generate session if not provided
            session_id = message_data.get("session", f"ws_{db_token.id}_{int(time.time())}")
            
            # Prepare chat request
            chat_request = MedicalChatRequest(
                message=message_data["message"],
                session=session_id,
                tools=message_data.get("tools"),
                prompt_mode=message_data.get("prompt_mode", "medical"),
                language=message_data.get("language", "auto")
            )
            
            # Process through medical API (reuse existing logic)
            try:
                # Get or create session
                db_session = await get_or_create_session(db, db_token.id, session_id)
                
                # Make request to medical API
                medical_request = {
                    "message": chat_request.message,
                    "session": chat_request.session,
                    "tools": chat_request.tools,
                    "prompt_mode": chat_request.prompt_mode,
                    "language": chat_request.language
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{MEDICAL_API_URL}/chat",
                        json=medical_request,
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        
                        # Update session stats
                        db_session.total_messages += 1
                        db.commit()
                        
                        # Send response back to client
                        await websocket.send_text(json.dumps({
                            "type": "chat_response",
                            "data": response_data,
                            "session_id": session_id
                        }))
                        
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Medical API error",
                            "status": response.status_code
                        }))
                        
            except Exception as e:
                logger.error(f"WebSocket processing error: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Processing error",
                    "details": str(e)
                }))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for token: {db_token.name}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()

# ============================================================================
# VOICE MODULE PROXY ENDPOINTS (chat3 — gm-voice:7003)
# ============================================================================

@app.post("/medical/voice/chunk", status_code=202)
async def voice_chunk_proxy(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    chunk_number: int = Form(...),
    tier: str = Form("classic"),
    db_token: Token = Depends(require_user_token),
    db: Session = Depends(get_db)
):
    """Forward audio chunk to voice module. Returns job_id immediately (async processing)."""
    start_time = time.time()

    valid_tiers = ["classic", "professional"]
    if tier not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Options: {valid_tiers}")

    try:
        audio_bytes = await audio.read()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VOICE_API_URL}/chunk",
                data={"session_id": session_id, "chunk_number": chunk_number, "tier": tier},
                files={"audio": (audio.filename, audio_bytes, audio.content_type)},
                timeout=30
            )

            response_data = response.json()
            processing_time = time.time() - start_time

            db_session = await get_or_create_session(db, db_token.id, session_id)
            db_session.total_messages += 1
            db.commit()

            await log_api_request(
                db=db,
                token_id=db_token.id,
                session_id=db_session.id,
                endpoint="/medical/voice/chunk",
                method="POST",
                request_data={"session_id": session_id, "chunk_number": chunk_number, "tier": tier},
                response_status=response.status_code,
                response_data=response_data,
                tokens_consumed=0,
                processing_time=processing_time,
                tool_used=f"voice_{tier}",
                prompt_mode=None,
                language_detected=None
            )

            if response.status_code in (200, 202):
                return response_data
            else:
                raise HTTPException(status_code=response.status_code, detail=response_data)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Voice module timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Voice module unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Voice chunk proxy error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/medical/voice/end")
async def voice_end_proxy(
    payload: dict,
    db_token: Token = Depends(require_user_token),
    db: Session = Depends(get_db)
):
    """Signal end of consultation. Voice module returns consolidated clinical document."""
    start_time = time.time()

    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=422, detail="session_id required")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VOICE_API_URL}/end",
                json={"session_id": session_id},
                timeout=60
            )

            response_data = response.json()
            processing_time = time.time() - start_time

            db_session = await get_or_create_session(db, db_token.id, session_id)
            db_session.is_active = False
            db.commit()

            await log_api_request(
                db=db,
                token_id=db_token.id,
                session_id=db_session.id,
                endpoint="/medical/voice/end",
                method="POST",
                request_data={"session_id": session_id},
                response_status=response.status_code,
                response_data=response_data,
                tokens_consumed=0,
                processing_time=processing_time,
                tool_used="voice_end",
                prompt_mode=None,
                language_detected=None
            )

            if response.status_code == 200:
                return response_data
            else:
                raise HTTPException(status_code=response.status_code, detail=response_data)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Voice module timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Voice module unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Voice end proxy error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/medical/voice/status/{session_id}")
async def voice_status_proxy(
    session_id: str,
    db_token: Token = Depends(require_user_token)
):
    """Poll for current document state during consultation."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{VOICE_API_URL}/status/{session_id}",
                timeout=10
            )
            return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Voice module unavailable: {str(e)}")


# ============================================================================
# CLINICAL SUMMARY PROXY ENDPOINT (chat2 — gm-ch-summary:7006)
# ============================================================================

class SummaryRequest(MedicalChatRequest):
    pass

@app.post("/medical/summary")
async def clinical_summary_proxy(
    request: SummaryRequest,
    db_token: Token = Depends(require_user_token),
    db: Session = Depends(get_db)
):
    """Proxy clinical summary requests to gm-ch-summary."""
    start_time = time.time()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SUMMARY_API_URL}/chat",
                json={"message": request.message, "prompt_mode": request.prompt_mode},
                timeout=60
            )
            response_data = response.json()
            processing_time = time.time() - start_time

            usage = response_data.get("usage", {})
            total_tokens = (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                            if isinstance(usage, dict) else 0)

            await log_api_request(
                db=db,
                token_id=db_token.id,
                session_id=None,
                endpoint="/medical/summary",
                method="POST",
                request_data={"message": request.message, "prompt_mode": request.prompt_mode},
                response_status=response.status_code,
                response_data=response_data,
                tokens_consumed=total_tokens,
                processing_time=processing_time,
                tool_used="summary",
                prompt_mode=request.prompt_mode,
                language_detected=None,
                input_tokens=usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0,
                output_tokens=usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0
            )
            update_token_usage(db, db_token.id, total_tokens)
            return response_data

    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Summary module unavailable: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )