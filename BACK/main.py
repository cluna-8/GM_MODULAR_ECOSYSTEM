# main.py - Enhanced version with GPT Formatting
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
    title="Healthcare Chat API - Multi-Provider with GPT Formatting",
    description="Secure chat backend with Azure OpenAI and OpenAI support + Medical Tools + GPT Formatting",
    version="1.1.0"
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

class GPTFormattingRequest(BaseModel):
    raw_data: str
    original_question: str
    tool_name: str
    extracted_term: str

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
            
            # Enhanced system prompt with medical tools awareness and multilingual support
            enhanced_system_prompt = (
                "You are a helpful healthcare assistant with access to medical databases and tools. "
                "You can search FDA drug information, PubMed literature, clinical trials, ICD-10 codes, "
                "and scrape medical websites when needed. "
                "Provide accurate, professional medical information while being empathetic and clear. "
                "Always recommend consulting healthcare professionals for medical decisions. "
                "When appropriate, use your medical tools to provide up-to-date information. "
                "Format your responses using markdown for better readability. "
                "IMPORTANT: Always respond in the same language as the user's question. "
                "If they ask in Spanish, respond in Spanish. If they ask in English, respond in English. "
                "Use proper medical terminology in the appropriate language."
            )
            
            # Create chat engine with memory
            chat_engine = SimpleChatEngine.from_defaults(
                llm=llm,
                memory=memory,
                system_prompt=enhanced_system_prompt
            )
            
            self.chat_engines[engine_key] = chat_engine
            
        return self.chat_engines[engine_key]

    async def format_medical_response_with_gpt(self, raw_data: str, original_question: str, tool_name: str, extracted_term: str) -> str:
        """Use GPT to format medical response with proper markdown"""
        # Detect language
        is_spanish = self._detect_spanish(original_question)
        response_language = "Spanish" if is_spanish else "English"
        
        formatting_prompt = f"""You are an expert medical information formatter. Your task is to take raw medical data and create a beautifully formatted, professional response using markdown.

ORIGINAL USER QUESTION: "{original_question}"
DETECTED LANGUAGE: {response_language}

RAW DATA FROM {tool_name.upper()}:
{raw_data}

LANGUAGE INSTRUCTION: 
- Respond in {response_language} to match the user's question language
- If Spanish: Use proper medical Spanish terminology and structure
- If English: Use standard English medical terminology

FORMATTING INSTRUCTIONS:
1. Create a clear, professional medical response in {response_language}
2. Use markdown formatting extensively:
   - **Bold** for important terms, drug names, conditions
   - *Italics* for medical terminology, scientific names
   - ### Headers for different sections
   - • Bullet points for lists
   - > Blockquotes for important warnings or notes

3. Structure the response with:
   - Brief introduction answering the user's question
   - Key information organized in sections
   - Important details highlighted
   - Professional medical disclaimer

4. Include relevant details from the search:
   - If FDA data: drug names, manufacturers, approval info, indications
   - If PubMed: study findings, research conclusions
   - If Clinical Trials: trial phases, conditions, recruitment status
   - If ICD-10: codes, descriptions, categories
   - If Web scraping: key medical information found

5. Make it visually appealing and easy to scan
6. End with appropriate medical disclaimer in {response_language}

CRITICAL: Your entire response must be written in {response_language}. Do not mix languages.

IMPORTANT: Format your response using proper markdown syntax. Make it professional but accessible.

Please format the response:"""

        # Create a temporary session for formatting
        formatting_session = f"formatting_{uuid.uuid4().hex[:8]}"
        chat_engine = self.get_or_create_chat_engine(formatting_session)
        
        try:
            response = await asyncio.to_thread(chat_engine.chat, formatting_prompt)
            return str(response)
        except Exception as e:
            print(f"GPT formatting error: {e}")
            # Fallback to basic formatting
            return self.basic_format_response(raw_data, original_question, tool_name, is_spanish)

    def _detect_spanish(self, text: str) -> bool:
        """Detect if text is in Spanish"""
        spanish_words = [
            'que', 'sobre', 'para', 'con', 'información', 'dime', 'quiero', 'necesito',
            'medicamento', 'medicina', 'dolor', 'enfermedad', 'síntoma', 'tratamiento',
            'salud', 'médico', 'hospital', 'pastilla', 'píldora', 'curar', 'aliviar',
            'cómo', 'cuándo', 'dónde', 'por', 'favor', 'ayuda', 'gracias',
            'aspirina', 'paracetamol', 'ibuprofeno', 'diabetes', 'hipertensión',
            'es', 'está', 'tiene', 'puede', 'debe', 'debería', 'podría'
        ]
        
        text_lower = text.lower()
        spanish_word_count = sum(1 for word in spanish_words if word in text_lower)
        
        # Also check for Spanish accents and ñ
        import re
        has_spanish_chars = bool(re.search(r'[ñáéíóúü]', text, re.IGNORECASE))
        
        # Consider it Spanish if it has Spanish words or Spanish characters
        return spanish_word_count >= 1 or has_spanish_chars

    def basic_format_response(self, raw_data: str, original_question: str, tool_name: str, is_spanish: bool = False) -> str:
        """Basic fallback formatting if GPT formatting fails"""
        if is_spanish:
            return f"""### Resultados de Búsqueda en {tool_name.upper()}

**Su Pregunta:** {original_question}

**Resultados:**
{raw_data}

---
> **Aviso Médico:** Esta información es solo para fines educativos. Siempre consulte con profesionales de la salud para decisiones médicas."""
        else:
            return f"""### {tool_name.upper()} Search Results

**Your Question:** {original_question}

**Results:**
{raw_data}

---
> **Medical Disclaimer:** This information is for educational purposes only. Always consult with healthcare professionals for medical decisions."""

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
            "medical_tools": medical_status["enabled_tools"],
            "gpt_formatting": "enabled"
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

# ============ ENHANCED MEDICAL TOOLS ENDPOINTS ============

# New GPT formatting endpoint
@app.post("/medical/format-response")
async def format_medical_response(request: GPTFormattingRequest):
    """Format medical response using GPT"""
    try:
        formatted_response = await chat_config.format_medical_response_with_gpt(
            request.raw_data,
            request.original_question,
            request.tool_name,
            request.extracted_term
        )
        
        return {
            "formatted_response": formatted_response,
            "original_question": request.original_question,
            "tool_used": request.tool_name,
            "extracted_term": request.extracted_term
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Formatting error: {str(e)}")

# MCP Management endpoints
@app.get("/mcp/status")
async def mcp_status():
    tools_status = chat_config.medical_tools.get_status()
    return {
        "medical_tools": tools_status,
        "current_provider": chat_config.provider_manager.current_provider,
        "integration_ready": True,
        "gpt_formatting": "enabled"
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

# ============ ENHANCED MCP + GPT INTEGRATION ENDPOINT ============

@app.post("/medical/enhanced-search")
async def enhanced_medical_search(
    query: str, 
    tool_name: str, 
    original_question: str = None,
    format_with_gpt: bool = True
):
    """
    Enhanced medical search with automatic GPT formatting
    This endpoint combines MCP search with GPT formatting in one call
    """
    try:
        # Validate tool
        available_tools = ["fda", "pubmed", "clinicaltrials", "icd10", "scraping"]
        if tool_name not in available_tools:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid tool. Available: {available_tools}"
            )
        
        # Perform MCP search based on tool
        raw_result = None
        
        if tool_name == "fda":
            raw_result = await chat_config.medical_tools.search_fda_drug(query)
        elif tool_name == "pubmed":
            raw_result = await chat_config.medical_tools.search_pubmed(query, max_results=3)
        elif tool_name == "clinicaltrials":
            raw_result = await chat_config.medical_tools.search_clinical_trials(query, max_results=3)
        elif tool_name == "icd10":
            raw_result = await chat_config.medical_tools.search_icd10(query)
        elif tool_name == "scraping":
            # Default to Mayo Clinic for scraping
            raw_result = await chat_config.medical_tools.scrape_medical_site(
                "https://www.mayoclinic.org", 
                query
            )
        
        if not raw_result:
            return {
                "error": f"No results found for '{query}' in {tool_name}",
                "raw_result": None,
                "formatted_result": None
            }
        
        # Format with GPT if requested
        formatted_result = None
        if format_with_gpt:
            try:
                formatted_result = await chat_config.format_medical_response_with_gpt(
                    raw_result,
                    original_question or query,
                    tool_name,
                    query
                )
            except Exception as format_error:
                print(f"GPT formatting failed: {format_error}")
                # Fallback to basic formatting
                formatted_result = chat_config.basic_format_response(
                    raw_result, 
                    original_question or query, 
                    tool_name
                )
        
        return {
            "success": True,
            "tool_used": tool_name,
            "search_term": query,
            "original_question": original_question,
            "raw_result": raw_result,
            "formatted_result": formatted_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Enhanced search failed: {str(e)}"
        )

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

# WebSocket endpoint with enhanced formatting
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
            
            # Check if this is an enhanced medical search request
            if message_data.get("enhanced_search"):
                try:
                    # Extract search parameters
                    tool_name = message_data.get("tool_name")
                    search_query = message_data.get("search_query")
                    original_message = message_data.get("message")
                    
                    # Perform enhanced search
                    search_result = await enhanced_medical_search(
                        query=search_query,
                        tool_name=tool_name,
                        original_question=original_message,
                        format_with_gpt=True
                    )
                    
                    # Send formatted response
                    response_data = {
                        "type": "enhanced_search_result",
                        "response": search_result["formatted_result"],
                        "raw_data": search_result["raw_result"],
                        "tool_used": tool_name,
                        "search_term": search_query,
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                        "provider": active_provider
                    }
                    
                except Exception as search_error:
                    response_data = {
                        "type": "error",
                        "response": f"Enhanced search failed: {str(search_error)}",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat()
                    }
            else:
                # Regular chat processing
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
                    "type": "chat_response",
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7005,
        reload=True,
        log_level="info"
    )