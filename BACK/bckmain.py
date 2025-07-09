# main.py - Fixed version with Medical Tools and CORS
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import json
import uuid
import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv

# LlamaIndex imports - Fixed
from llama_index.core import Settings
from llama_index.core.chat_engine import SimpleChatEngine
from llama_index.core.memory import ChatMemoryBuffer

# Redis for session management
import redis.asyncio as redis

# Local imports
from providers import ProviderManager, ProviderType
from mcp.medical_tools import MedicalTools

# Load environment variables
load_dotenv()

# Create FastAPI app (SOLO UNA VEZ)
app = FastAPI(
    title="Healthcare Chat API - Multi-Provider",
    description="Secure chat backend with Azure OpenAI and OpenAI support + Medical Tools",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ChatMessage(BaseModel):
    message: str
    session_id: str
    user_id: Optional[str] = None
    context: Optional[Dict] = None
    provider: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime
    provider: str
    tokens_used: Optional[int] = None

class SessionInfo(BaseModel):
    session_id: str
    created_at: datetime
    message_count: int
    last_activity: datetime
    provider: str

class ProviderSwitchRequest(BaseModel):
    provider: str

# Global configurations
class ChatConfig:
    def __init__(self):
        self.provider_manager = None
        self.redis_client = None
        self.chat_engines: Dict[str, SimpleChatEngine] = {}
        self.medical_tools = MedicalTools()
        
    async def initialize(self):
        """Initialize provider manager and Redis connections"""
        try:
            # Initialize provider manager
            self.provider_manager = ProviderManager()
            
            # Set global settings with current provider
            current_provider = self.provider_manager.get_current_provider()
            Settings.llm = current_provider.get_llm()
            Settings.embed_model = current_provider.get_embedding()
            
            # Initialize Redis
            self.redis_client = redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                decode_responses=True
            )
            
            # Initialize medical tools
            await self.medical_tools.initialize()
            
            print("✅ Chat configuration initialized successfully")
            print(f"🎯 Active provider: {self.provider_manager.current_provider}")
            
        except Exception as e:
            print(f"❌ Error initializing chat config: {e}")
            raise

    def switch_provider(self, provider_name: str) -> bool:
        """Switch to a different provider and update global settings"""
        if not self.provider_manager.set_provider(provider_name):
            return False
        
        # Update global settings
        current_provider = self.provider_manager.get_current_provider()
        Settings.llm = current_provider.get_llm()
        Settings.embed_model = current_provider.get_embedding()
        
        # Clear existing chat engines to use new provider
        self.chat_engines.clear()
        
        return True

    def get_or_create_chat_engine(self, session_id: str, provider_override: str = None) -> SimpleChatEngine:
        """Get existing chat engine or create new one for session"""
        # Use provider override if specified and valid
        if provider_override and provider_override in self.provider_manager.get_available_providers():
            temp_provider = self.provider_manager.providers[provider_override]
            llm = temp_provider.get_llm()
        else:
            llm = Settings.llm
        
        engine_key = f"{session_id}_{provider_override or self.provider_manager.current_provider}"
        
        if engine_key not in self.chat_engines:
            # Create memory buffer - FIXED VERSION
            try:
                memory = ChatMemoryBuffer.from_defaults(
                    token_limit=3000
                    # Removed problematic tokenizer_fn
                )
            except Exception:
                # Fallback: create memory without token limit
                memory = ChatMemoryBuffer.from_defaults()
            
            # Enhanced system prompt with medical tools awareness
            enhanced_system_prompt = (
                "You are a helpful healthcare assistant with access to medical databases and tools. "
                "You can search FDA drug information, PubMed literature, clinical trials, ICD-10 codes, "
                "and scrape medical websites when needed. "
                "Provide accurate, professional medical information while being empathetic and clear. "
                "Always recommend consulting healthcare professionals for medical decisions. "
                "When appropriate, use your medical tools to provide up-to-date information."
            )
            
            # Create chat engine with memory
            chat_engine = SimpleChatEngine.from_defaults(
                llm=llm,
                memory=memory,
                system_prompt=enhanced_system_prompt
            )
            
            self.chat_engines[engine_key] = chat_engine
            
        return self.chat_engines[engine_key]

    async def save_session_info(self, session_id: str, message_count: int, provider: str):
        """Save session metadata to Redis"""
        if self.redis_client:
            session_data = {
                "session_id": session_id,
                "message_count": message_count,
                "last_activity": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "provider": provider
            }
            await self.redis_client.hset(
                f"session:{session_id}", 
                mapping=session_data
            )
            # Set expiration (24 hours)
            await self.redis_client.expire(f"session:{session_id}", 86400)

    async def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session metadata from Redis"""
        if self.redis_client:
            session_data = await self.redis_client.hgetall(f"session:{session_id}")
            return session_data if session_data else None
        return None

# Global chat configuration
chat_config = ChatConfig()

# Startup event
@app.on_event("startup")
async def startup_event():
    await chat_config.initialize()

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    if chat_config.redis_client:
        await chat_config.redis_client.close()
    await chat_config.medical_tools.cleanup()

# Health check endpoint
@app.get("/health")
async def health_check():
    medical_status = chat_config.medical_tools.get_status()
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "services": {
            "current_provider": chat_config.provider_manager.current_provider,
            "available_providers": chat_config.provider_manager.get_available_providers(),
            "redis": "connected" if chat_config.redis_client else "disconnected",
            "medical_tools": medical_status["enabled_tools"]
        }
    }

# Provider management endpoints
@app.get("/providers")
async def list_providers():
    """List all available providers and their status"""
    providers = []
    for provider_name in chat_config.provider_manager.get_available_providers():
        info = chat_config.provider_manager.get_provider_info(provider_name)
        info["is_current"] = provider_name == chat_config.provider_manager.current_provider
        providers.append(info)
    
    return {"providers": providers}

@app.get("/providers/current")
async def get_current_provider():
    """Get current active provider information"""
    return chat_config.provider_manager.get_provider_info()

@app.post("/providers/switch")
async def switch_provider(request: ProviderSwitchRequest):
    """Switch to a different provider"""
    if request.provider not in chat_config.provider_manager.get_available_providers():
        raise HTTPException(
            status_code=400, 
            detail=f"Provider '{request.provider}' not available. Available: {chat_config.provider_manager.get_available_providers()}"
        )
    
    success = chat_config.switch_provider(request.provider)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to switch provider")
    
    return {
        "message": f"Successfully switched to {request.provider}",
        "provider_info": chat_config.provider_manager.get_provider_info()
    }

# Chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatMessage):
    try:
        # Generate session ID if not provided
        if not request.session_id:
            request.session_id = str(uuid.uuid4())
        
        # Determine which provider to use
        active_provider = request.provider or chat_config.provider_manager.current_provider
        
        # Get or create chat engine for this session
        chat_engine = chat_config.get_or_create_chat_engine(
            request.session_id, 
            request.provider
        )
        
        # Process the message
        response = await asyncio.to_thread(
            chat_engine.chat, 
            request.message
        )
        
        # Save session info
        session_info = await chat_config.get_session_info(request.session_id)
        message_count = int(session_info.get("message_count", 0)) + 1 if session_info else 1
        await chat_config.save_session_info(request.session_id, message_count, active_provider)
        
        return ChatResponse(
            response=str(response),
            session_id=request.session_id,
            timestamp=datetime.now(),
            provider=active_provider,
            tokens_used=None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

# Get session info
@app.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    session_info = await chat_config.get_session_info(session_id)
    
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionInfo(
        session_id=session_info["session_id"],
        created_at=datetime.fromisoformat(session_info["created_at"]),
        message_count=int(session_info["message_count"]),
        last_activity=datetime.fromisoformat(session_info["last_activity"]),
        provider=session_info.get("provider", "unknown")
    )

# List active sessions
@app.get("/sessions")
async def list_sessions():
    if not chat_config.redis_client:
        return {"sessions": []}
    
    session_keys = await chat_config.redis_client.keys("session:*")
    sessions = []
    
    for key in session_keys:
        session_data = await chat_config.redis_client.hgetall(key)
        if session_data:
            sessions.append({
                "session_id": session_data["session_id"],
                "message_count": int(session_data["message_count"]),
                "last_activity": session_data["last_activity"],
                "provider": session_data.get("provider", "unknown")
            })
    
    return {"sessions": sessions}

# Clear session
@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    try:
        # Remove from in-memory chat engines (all provider variants)
        keys_to_remove = [k for k in chat_config.chat_engines.keys() if k.startswith(session_id)]
        for key in keys_to_remove:
            del chat_config.chat_engines[key]
        
        # Remove from Redis
        if chat_config.redis_client:
            await chat_config.redis_client.delete(f"session:{session_id}")
        
        return {"message": f"Session {session_id} cleared successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing session: {str(e)}")

# WebSocket endpoint
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Get provider from message or use default
            provider_override = message_data.get("provider")
            active_provider = provider_override or chat_config.provider_manager.current_provider
            
            # Get or create chat engine
            chat_engine = chat_config.get_or_create_chat_engine(session_id, provider_override)
            
            # Process message
            response = await asyncio.to_thread(
                chat_engine.chat,
                message_data["message"]
            )
            
            # Update session info
            session_info = await chat_config.get_session_info(session_id)
            message_count = int(session_info.get("message_count", 0)) + 1 if session_info else 1
            await chat_config.save_session_info(session_id, message_count, active_provider)
            
            # Send response
            response_data = {
                "response": str(response),
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "message_count": message_count,
                "provider": active_provider
            }
            
            await websocket.send_text(json.dumps(response_data))
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()

# ============ MEDICAL TOOLS ENDPOINTS ============

# MCP Management endpoints
@app.get("/mcp/status")
async def mcp_status():
    tools_status = chat_config.medical_tools.get_status()
    return {
        "medical_tools": tools_status,
        "current_provider": chat_config.provider_manager.current_provider,
        "integration_ready": True
    }

# Medical endpoints for direct testing
@app.post("/medical/fda-search")
async def fda_search(drug_name: str):
    """Buscar medicamento en FDA"""
    result = await chat_config.medical_tools.search_fda_drug(drug_name)
    return {"result": result}

@app.post("/medical/pubmed-search") 
async def pubmed_search(query: str, max_results: int = 3):
    """Buscar en PubMed"""
    result = await chat_config.medical_tools.search_pubmed(query, max_results)
    return {"result": result}

@app.post("/medical/clinical-trials")
async def clinical_trials_search(condition: str, max_results: int = 3):
    """Buscar ensayos clínicos"""
    result = await chat_config.medical_tools.search_clinical_trials(condition, max_results)
    return {"result": result}

@app.post("/medical/icd10-search")
async def icd10_search(term: str):
    """Buscar códigos ICD-10"""
    result = await chat_config.medical_tools.search_icd10(term)
    return {"result": result}

@app.post("/medical/scrape-site")
async def scrape_site(url: str, search_term: str = None):
    """Hacer scraping de sitio médico"""
    result = await chat_config.medical_tools.scrape_medical_site(url, search_term)
    return {"result": result}

@app.get("/medical/tools")
async def list_medical_tools():
    """Listar herramientas médicas disponibles"""
    return chat_config.medical_tools.get_available_functions()

@app.post("/medical/tools/{tool_name}/enable")
async def enable_medical_tool(tool_name: str):
    """Habilitar herramienta médica específica"""
    success = chat_config.medical_tools.enable_tool(tool_name)
    if success:
        return {"message": f"Tool {tool_name} enabled successfully"}
    else:
        raise HTTPException(status_code=400, detail=f"Invalid tool name: {tool_name}")

@app.post("/medical/tools/{tool_name}/disable")
async def disable_medical_tool(tool_name: str):
    """Deshabilitar herramienta médica específica"""
    success = chat_config.medical_tools.disable_tool(tool_name)
    return {"message": f"Tool {tool_name} disabled"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7005,
        reload=True,
        log_level="info"
    )
