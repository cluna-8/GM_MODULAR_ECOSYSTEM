# main.py - Healthcare Chatbot with Hybrid Architecture
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
import json
import uuid
import asyncio
from datetime import datetime
import os
import logging
from dotenv import load_dotenv
import re
import string
import yaml
import aiohttp

# LlamaIndex imports
from llama_index.core import Settings
from llama_index.core.chat_engine import SimpleChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.storage.chat_store.redis import RedisChatStore
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
import tiktoken

# Redis for session management
import redis.asyncio as redis

# Local imports - New Models and Managers
from models import (
    ChatRequest,
    ToolRequest,
    StandardResponse,
    ChatResponse,
    ToolResponse,
    ErrorResponse,
    HealthCheck,
    ProviderInfo,
    SessionInfo,
    PromptMode,
    ToolType,
    ResponseStatus,
    ConversationMemory,
    FeedbackRequest,
    create_success_response,
    create_error_response,
)
from providers import ProviderManager
from mcp.medical_tools import get_medical_tools, MedicalTools
from prompt_manager import get_prompt_manager, PromptManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Healthcare Chat API - Hybrid Architecture",
    description="Advanced healthcare chatbot with unified chat endpoint and specialized medical tools",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Medical Auditor Client
class MedicalAuditorClient:
    """Client to communicate with the independent Medical Auditor microservice"""

    def __init__(self, base_url: str = "http://medical-auditor:8001"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def audit_pre_process(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Audit the input before LLM processing"""
        try:
            session = await self.get_session()
            payload = {"text": text}
            if context:
                payload["context"] = context
            async with session.post(
                f"{self.base_url}/audit/pre-process", json=payload
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {"status": "OK", "verdict": "Auditor unavailable (skipped)"}
        except Exception as e:
            logger.warning(f"Auditor pre-process failed: {e}")
            return {"status": "OK", "verdict": "Auditor failed (skipped)"}

    async def audit_validate_safety(
        self, response_text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Audit the output for safety against HIS context"""
        try:
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}/audit/validate-safety",
                json={"text": response_text, "context": context},
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {"status": "OK", "verdict": "Auditor unavailable (skipped)"}
        except Exception as e:
            logger.warning(f"Auditor safety validation failed: {e}")
            return {"status": "OK", "verdict": "Auditor failed (skipped)"}

    async def cleanup(self):
        if self.session and not self.session.closed:
            await self.session.close()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
import aiohttp

# ============================================================================
# GLOBAL CONFIGURATION CLASS
# ============================================================================


class HybridChatConfig:
    """Configuration class for hybrid architecture"""

    def __init__(self):
        self.provider_manager: Optional[ProviderManager] = None
        self.redis_client: Optional[redis.Redis] = None
        self.chat_store: Optional[RedisChatStore] = (
            None  # NEW: For conversation persistence
        )
        self.medical_tools: Optional[MedicalTools] = None
        self.prompt_manager: Optional[PromptManager] = None
        self.token_counter: Optional[TokenCountingHandler] = None
        self.chat_engines: Dict[str, SimpleChatEngine] = {}
        self.tool_extraction_cache: Dict[str, str] = {}  # Cache de normalización
        self.auditor: Optional[MedicalAuditorClient] = None
        self.initialized = False

    async def initialize(self):
        """Initialize all components of the hybrid system"""
        try:
            logger.info("🚀 Initializing Hybrid Chat System...")

            # 1. Initialize Provider Manager
            self.provider_manager = ProviderManager()
            current_provider = self.provider_manager.get_current_provider()
            Settings.llm = current_provider.get_llm()
            Settings.embed_model = current_provider.get_embedding()

            # 1.1 Initialize Token Counter
            self.token_counter = TokenCountingHandler(
                tokenizer=tiktoken.encoding_for_model("gpt-3.5-turbo").encode
            )
            Settings.callback_manager = CallbackManager([self.token_counter])

            logger.info(
                f"✅ Provider Manager initialized - Active: {self.provider_manager.current_provider}"
            )

            # 2. Initialize Redis
            try:
                self.redis_client = redis.from_url(
                    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                    decode_responses=True,
                )
                # Test connection
                await self.redis_client.ping()
                logger.info("✅ Redis connection established")

                # Initialize RedisChatStore for conversation persistence
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                self.chat_store = RedisChatStore(
                    redis_url=redis_url, ttl=604800  # 7 days
                )
                logger.info(
                    "✅ RedisChatStore initialized for conversation persistence"
                )
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed: {e}")
                self.redis_client = None

            # 3. Initialize Medical Tools
            self.medical_tools = await get_medical_tools()
            logger.info("✅ Medical Tools initialized")

            # 4. Initialize Prompt Manager
            self.prompt_manager = await get_prompt_manager(self.redis_client)
            logger.info("✅ Prompt Manager initialized")

            # 5. Initialize Medical Auditor Client
            self.auditor = MedicalAuditorClient(
                os.getenv("AUDITOR_URL", "http://medical-auditor:8001")
            )
            logger.info("✅ Medical Auditor initialized")

            self.initialized = True
            logger.info("🎯 Hybrid Chat System fully initialized!")

        except Exception as e:
            logger.error(f"❌ Error initializing Hybrid Chat System: {e}")
            raise

    async def get_or_create_chat_engine(
        self,
        session_id: str,
        prompt_mode: PromptMode,
        custom_system_prompt: Optional[str] = None,
    ) -> SimpleChatEngine:
        """Get or create chat engine with specific prompt mode and optional custom system prompt"""
        engine_key = (
            f"{session_id}_{prompt_mode.value}_{self.provider_manager.current_provider}"
        )

        # Si hay un prompt customizado, forzamos la creación o actualización si es distinto
        if engine_key not in self.chat_engines or custom_system_prompt:
            try:
                # Obtener la memoria si ya existía el motor para no perder el hilo
                existing_memory = None
                if engine_key in self.chat_engines:
                    engine = self.chat_engines[engine_key]
                    # LlamaIndex versions vary: some use .memory, some ._memory, some store it in chat_history
                    existing_memory = getattr(
                        engine, "memory", getattr(engine, "_memory", None)
                    )

                    # Log if memory was found
                    if existing_memory:
                        logger.debug(f"Reusing existing memory for {engine_key}")
                    else:
                        logger.warning(
                            f"Could not find memory attribute in existing engine {engine_key}"
                        )

                # Get prompt configuration
                prompt_config = await self.prompt_manager.get_prompt(prompt_mode)

                # Usar el prompt customizado si se provee, sino el del config
                system_prompt = (
                    custom_system_prompt
                    if custom_system_prompt
                    else prompt_config.system_prompt
                )

                # Create memory with RedisChatStore for automatic persistence
                # Use session_id as chat_store_key for continuity across restarts
                chat_store_key = f"chat_{session_id}"

                if existing_memory:
                    # Reuse existing memory if engine is already in cache
                    memory = existing_memory
                    logger.debug(f"Reusing in-memory buffer for {engine_key}")
                else:
                    # Create new memory with RedisChatStore for automatic persistence
                    try:
                        if self.chat_store:
                            memory = ChatMemoryBuffer.from_defaults(
                                chat_store=self.chat_store,
                                chat_store_key=chat_store_key,
                                token_limit=3000,
                            )
                            logger.info(
                                f"Created memory with RedisChatStore for {chat_store_key}"
                            )
                        else:
                            # Fallback if RedisChatStore is not available
                            memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
                            logger.warning(
                                f"RedisChatStore not available, using in-memory buffer for {engine_key}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to create memory with chat store: {e}, using default"
                        )
                        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)

                # Create chat engine with custom prompt
                chat_engine = SimpleChatEngine.from_defaults(
                    llm=Settings.llm,
                    memory=memory,
                    system_prompt=system_prompt,
                )

                # Store chat engine
                self.chat_engines[engine_key] = chat_engine
                logger.debug(f"Created/Updated chat engine: {engine_key}")

            except Exception as e:
                logger.error(f"Error creating chat engine: {e}")
                raise

        return self.chat_engines[engine_key]

    def detect_language(self, text: str) -> str:
        """Detect language of input text"""
        spanish_indicators = [
            "que",
            "qué",
            "para",
            "con",
            "sobre",
            "dime",
            "quiero",
            "necesito",
            "información",
            "medicina",
            "medicamento",
            "dolor",
            "enfermedad",
            "síntoma",
            "tratamiento",
            "salud",
            "médico",
            "hospital",
            "cómo",
            "cuándo",
            "dónde",
            "por",
            "favor",
            "ayuda",
            "gracias",
            "es",
            "está",
        ]

        text_lower = text.lower()
        spanish_count = sum(1 for word in spanish_indicators if word in text_lower)

        # Check for Spanish characters
        import re

        has_spanish_chars = bool(re.search(r"[ñáéíóúü¿¡]", text, re.IGNORECASE))

        return "es" if spanish_count >= 1 or has_spanish_chars else "en"

    async def save_conversation_memory(
        self, session_id: str, memory: ConversationMemory
    ) -> bool:
        """Save conversation to Redis for persistence"""
        if not self.redis_client:
            return False

        try:
            memory_key = f"conversation:{session_id}"
            memory_data = memory.model_dump_json()

            # Add to conversation list
            await self.redis_client.lpush(memory_key, memory_data)

            # Keep only last 50 messages
            await self.redis_client.ltrim(memory_key, 0, 49)

            # Set expiration (7 days)
            await self.redis_client.expire(memory_key, 604800)

            return True

        except Exception as e:
            logger.error(f"Error saving conversation memory: {e}")
            return False

    async def update_session_info(
        self,
        session_id: str,
        tool_used: Optional[ToolType] = None,
        prompt_mode: Optional[PromptMode] = None,
    ) -> bool:
        """Update session information in Redis"""
        if not self.redis_client:
            return False

        try:
            session_key = f"session:{session_id}"

            # Get existing session or create new
            existing_data = await self.redis_client.hgetall(session_key)

            session_data = {
                "session_id": session_id,
                "last_activity": datetime.now().isoformat(),
                "provider": self.provider_manager.current_provider,
                "message_count": str(int(existing_data.get("message_count", "0")) + 1),
            }

            # Add creation time if new session
            if not existing_data:
                session_data["created_at"] = datetime.now().isoformat()
                tools_used = []
                modes_used = []
            else:
                session_data["created_at"] = existing_data.get(
                    "created_at", datetime.now().isoformat()
                )

                # Parse existing arrays safely
                try:
                    tools_used = json.loads(existing_data.get("tools_used", "[]"))
                except (json.JSONDecodeError, TypeError):
                    tools_used = []

                try:
                    modes_used = json.loads(
                        existing_data.get("prompt_modes_used", "[]")
                    )
                except (json.JSONDecodeError, TypeError):
                    modes_used = []

            # Update tools used
            if tool_used and tool_used.value not in tools_used:
                tools_used.append(tool_used.value)
            session_data["tools_used"] = json.dumps(tools_used)

            # Update prompt modes used
            if prompt_mode and prompt_mode.value not in modes_used:
                modes_used.append(prompt_mode.value)
            session_data["prompt_modes_used"] = json.dumps(modes_used)

            await self.redis_client.hset(session_key, mapping=session_data)
            await self.redis_client.expire(session_key, 86400)  # 24 hours

            logger.debug(
                f"Updated session {session_id}: tools={tools_used}, modes={modes_used}"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating session info: {e}")
            return False

    async def save_audit_trace(self, session_id: str, step: str, data: Any) -> bool:
        """Save a step of the audit trace in Redis"""
        if not self.redis_client:
            return False
        try:
            trace_key = f"audit_trace:{session_id}"
            trace_entry = {
                "step": step,
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }
            await self.redis_client.rpush(trace_key, json.dumps(trace_entry))
            await self.redis_client.expire(trace_key, 86400)  # 24h
            return True
        except Exception as e:
            logger.error(f"Error saving audit trace: {e}")
            return False

    async def get_audit_trace(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve the audit trace for a session"""
        if not self.redis_client:
            return []
        try:
            trace_key = f"audit_trace:{session_id}"
            steps = await self.redis_client.lrange(trace_key, 0, -1)
            return [json.loads(s) for s in steps]
        except Exception as e:
            logger.error(f"Error getting audit trace: {e}")
            return []

    async def log_trace_to_file(self, session_id: str) -> bool:
        """Append the full session trace to a persistent JSONL file and flag anomalies"""
        try:
            trace = await self.get_audit_trace(session_id)
            if not trace:
                return False

            log_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(log_dir, exist_ok=True)

            # 1. Log Forense General
            log_file = os.path.join(log_dir, "audit_log.jsonl")
            entry = {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "full_trace": trace,
            }

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            # 2. Detección Proactiva de Anomalías (Para Re-entrenamiento)
            # Buscamos alertas o rechazos en el trazo
            is_anomaly = False
            audit_reason = ""
            for step in trace:
                if step.get("step") in [
                    "AUDITOR_PRE_PROCESS",
                    "AUDITOR_SAFETY_VALIDATION",
                ]:
                    data = step.get("data", {})
                    if data.get("status") in ["REJECTED", "ALERT"]:
                        is_anomaly = True
                        audit_reason = data.get("verdict")
                        break

            if is_anomaly:
                anomaly_file = os.path.join(log_dir, "anomalies.jsonl")
                anomaly_entry = {
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "reason": audit_reason,
                    "trace": trace,
                }
                with open(anomaly_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(anomaly_entry, ensure_ascii=False) + "\n")
                logger.warning(
                    f"🚨 Anomaly detected in session {session_id} and flagged for review."
                )

            logger.info(f"Trace for {session_id} persisted to file.")
            return True
        except Exception as e:
            logger.error(f"Error persisting trace to file: {e}")
            return False

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up Hybrid Chat System...")

        if self.medical_tools:
            await self.medical_tools.cleanup()

        if self.prompt_manager:
            await self.prompt_manager.cleanup()

        if self.auditor:
            await self.auditor.cleanup()

        if self.redis_client:
            await self.redis_client.close()

        self.chat_engines.clear()


# Global configuration instance
chat_config = HybridChatConfig()

# ============================================================================
# STARTUP AND SHUTDOWN EVENTS
# ============================================================================


@app.on_event("startup")
async def startup_event():
    await chat_config.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    await chat_config.cleanup()


# ============================================================================
# HEALTH CHECK AND SYSTEM STATUS
@app.get("/audit/trace/{session_id}")
async def get_audit_trace(session_id: str):
    """Retrieve the full audit trace for a specific session"""
    trace = await chat_config.get_audit_trace(session_id)
    if not trace:
        raise HTTPException(
            status_code=404, detail="Trace not found or session expired"
        )
    return {"session_id": session_id, "trace": trace}


@app.post("/audit/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Expert medical feedback (RLHF)
    Captures professional corrections for future model training
    """
    try:
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        training_file = os.path.join(log_dir, "training_data.jsonl")

        # Intentar obtener el trazo original para enriquecer el feedback
        trace = await chat_config.get_audit_trace(request.session_id)

        feedback_entry = {
            "session_id": request.session_id,
            "expert_id": request.expert_id,
            "rating": request.rating,
            "is_dangerous": request.is_dangerous,
            "comment": request.comment,
            "suggested_response": request.suggested_response,
            "timestamp": datetime.now().isoformat(),
            "original_trace": trace,
        }

        with open(training_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")

        logger.info(f"✅ Medical feedback received for session {request.session_id}")
        return {"status": "success", "message": "Feedback registered for training"}
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")


# ============================================================================


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Comprehensive health check for all system components"""
    services_status = {
        "provider_manager": {
            "status": "healthy" if chat_config.provider_manager else "error",
            "current_provider": (
                chat_config.provider_manager.current_provider
                if chat_config.provider_manager
                else None
            ),
            "available_providers": (
                chat_config.provider_manager.get_available_providers()
                if chat_config.provider_manager
                else []
            ),
        },
        "redis": {
            "status": "connected" if chat_config.redis_client else "disconnected",
            "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        },
        "medical_tools": {
            "status": "healthy" if chat_config.medical_tools else "error",
            "enabled_tools": (
                list(chat_config.medical_tools.enabled_tools)
                if chat_config.medical_tools
                else []
            ),
            "session_active": (
                chat_config.medical_tools.session is not None
                if chat_config.medical_tools
                else False
            ),
        },
        "prompt_manager": {
            "status": "healthy" if chat_config.prompt_manager else "error",
            "prompts_loaded": (
                len(chat_config.prompt_manager.prompts_cache)
                if chat_config.prompt_manager
                else 0
            ),
            "yaml_exists": (
                chat_config.prompt_manager.yaml_path.exists()
                if chat_config.prompt_manager
                else False
            ),
        },
        "chat_engines": {
            "active_engines": len(chat_config.chat_engines),
            "status": "healthy",
        },
    }

    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        services=services_status,
        version="2.0.0",
    )


# ============================================================================
# HYBRID CHAT ENDPOINT - MAIN UNIFIED ENDPOINT
# ============================================================================


@app.post("/chat", response_model=ChatResponse)
async def unified_chat_endpoint(request: ChatRequest):
    """
    Unified chat endpoint that handles:
    1. General conversation (no tools)
    2. Tool-enhanced conversation (with MCP tools)
    3. Different prompt modes (medical, pediatric, emergency, etc.)
    """
    try:
        # Generate session ID if not provided
        if not request.session:
            request.session = f"chat_{uuid.uuid4().hex[:12]}"

        # Detect language if auto
        detected_language = chat_config.detect_language(request.message)

        # 🎯 AUDIT TRACE: Init
        await chat_config.save_audit_trace(
            request.session,
            "INPUT_RECEIVED",
            {
                "message": request.message,
                "context": request.context,
                "prompt_mode": request.prompt_mode.value,
            },
        )

        # 🎯 PUNTO 1: Inyección de Contexto HIS en el System Prompt (Mejora de Seguridad)
        # 1. Formatear bloque HIS
        context_block = ""
        if request.context:
            context_items = []
            for k, v in request.context.items():
                key_pretty = k.replace("_", " ").title()
                context_items.append(f"• {key_pretty}: {v}")
            context_block = "\n".join(context_items)
            logger.info(f"Contexto HIS formateado para sesión {request.session}")
        else:
            context_block = "No hay datos del paciente disponibles para esta consulta."

        # 2. Obtener prompt base y reemplazar placeholder
        prompt_config = await chat_config.prompt_manager.get_prompt(request.prompt_mode)
        system_prompt_filled = prompt_config.system_prompt.replace(
            "{{HIS_DATA}}", context_block
        )

        # 🎯 AUDIT TRACE: Prompt Injection (Verificación)
        await chat_config.save_audit_trace(
            request.session,
            "SYSTEM_PROMPT_INJECTED",
            {"system_prompt": system_prompt_filled},
        )

        # 3. Obtener o actualizar motor con el system prompt YA cargado con contexto
        chat_engine = await chat_config.get_or_create_chat_engine(
            request.session,
            request.prompt_mode,
            custom_system_prompt=system_prompt_filled,
        )

        # 🎯 Obtener historial de memoria para la auditoría (hasta 4 mensajes recientes)
        memory_context = None
        try:
            history = chat_engine.memory.get()
            if history:
                recent_msgs = [
                    f"{m.role}: {m.content}"
                    for m in history[-4:]
                    if m.role in ["user", "assistant"]
                ]
                if recent_msgs:
                    memory_context = "\n".join(recent_msgs)
        except Exception as e:
            logger.warning(
                f"No se pudo extraer el historial de memoria para auditoría: {e}"
            )

        # 🎯 STEP 1: Medical Auditor Pre-Analysis
        audit_context = {"memory": memory_context} if memory_context else None
        audit_pre = await chat_config.auditor.audit_pre_process(
            request.message, context=audit_context
        )

        # 🎯 AUDIT TRACE: Pre-Audit
        await chat_config.save_audit_trace(
            request.session,
            "AUDITOR_PRE_PROCESS",
            {
                "status": audit_pre.get("status"),
                "verdict": audit_pre.get("verdict"),
                "reasoning": audit_pre.get("reasoning"),
                "risk_level": audit_pre.get("risk_level"),
                "is_safe": audit_pre.get("is_safe"),
            },
        )

        if audit_pre.get("status") == "REJECTED":
            # 🎯 PERSISTENT LOGGING: Save even if intercepted
            await chat_config.log_trace_to_file(request.session)

            return ChatResponse(
                status=ResponseStatus.SUCCESS,
                data={"response": audit_pre.get("verdict"), "auditor_intercept": True},
                message="Petición bloqueada por redundancia o incoherencia clínica",
                session_id=request.session,
                timestamp=datetime.now(),
            )

        # El user_message ahora es SOLAMENTE la consulta clínica, sin mezclar con el HIS
        # Esto evita el Recency Bias y mejora la adherencia del modelo
        final_message = request.message

        response_data = {}
        tool_used = None
        raw_tool_data = None
        llm_response_obj = None

        # Check if specific tool is requested
        if request.tools:
            logger.info(f"Processing tool-enhanced request: {request.tools.value}")

            # Execute tool search (now extracts and normalizes internally)
            tool_result = await execute_tool_search(request.tools, request.message)

            if tool_result.success:
                # Lógica especial para ICD-10: respuesta directa sin LLM
                if request.tools == ToolType.ICD10:
                    # Para ICD-10, usar datos directos de la herramienta tal como vienen
                    response_data["response"] = tool_result.processed_result
                    tool_used = request.tools
                    raw_tool_data = tool_result.raw_result

                else:
                    # Para otras herramientas, usar prompt específico del YAML
                    tool_prompt_config = (
                        await chat_config.prompt_manager.get_tool_prompt(request.tools)
                    )

                    # El tool prompt ya incluye user_message, que ahora será el mensaje final con contexto
                    enhanced_prompt = tool_prompt_config.format(
                        user_message=final_message,
                        tool_data=tool_result.processed_result,
                    )

                    llm_response_obj = await asyncio.to_thread(
                        chat_engine.chat, enhanced_prompt
                    )
                    response_data["response"] = str(llm_response_obj)
                    tool_used = request.tools
                    raw_tool_data = tool_result.raw_result
            else:
                # Tool failed, use regular chat
                logger.warning(
                    f"Tool {request.tools.value} failed: {tool_result.error_message}"
                )
                llm_response_obj = await asyncio.to_thread(
                    chat_engine.chat, final_message
                )
                response_data["response"] = str(llm_response_obj)
                response_data["tool_error"] = tool_result.error_message
        else:
            # Regular chat without tools
            llm_response_obj = await asyncio.to_thread(chat_engine.chat, final_message)
            response_data["response"] = str(llm_response_obj)

        # 🎯 AUDIT TRACE: LLM Raw Output
        await chat_config.save_audit_trace(
            request.session, "LLM_RAW_OUTPUT", {"response": response_data["response"]}
        )

        # 🎯 STEP 2: Medical Auditor Safety Validation
        # Validar la respuesta contra el HIS para evitar contraindicaciones
        audit_safety = await chat_config.auditor.audit_validate_safety(
            response_data["response"], request.context
        )

        # 🎯 AUDIT TRACE: Safety Validation
        await chat_config.save_audit_trace(
            request.session,
            "AUDITOR_SAFETY_VALIDATION",
            {
                "status": audit_safety.get("status"),
                "verdict": audit_safety.get("verdict"),
                "reasoning": audit_safety.get("reasoning"),
                "risk_level": audit_safety.get("risk_level"),
                "is_safe": audit_safety.get("is_safe"),
            },
        )

        if audit_safety.get("status") == "ALERT":
            # Adjuntar alerta del auditor a la respuesta original
            alerta = audit_safety.get("verdict")
            response_data["response"] = (
                f"{response_data['response']}\n\n⚠️ **AUDITORÍA CLÍNICA:** {alerta}"
            )
            response_data["auditor_alert"] = True

        # 🎯 AUDIT TRACE: Final Response
        await chat_config.save_audit_trace(
            request.session, "FINAL_RESPONSE_SERVED", response_data
        )

        # 🎯 PERSISTENT LOGGING: Save to JSONL for monitoring/RLHF
        asyncio.create_task(chat_config.log_trace_to_file(request.session))

        # Save conversation memory
        conversation_memory = ConversationMemory(
            user_message=request.message,
            tool_used=tool_used,
            raw_tool_data=raw_tool_data,
            assistant_response=response_data["response"],
            timestamp=datetime.now(),
            prompt_mode=request.prompt_mode,
            metadata={"language": detected_language, "session": request.session},
        )
        await chat_config.save_conversation_memory(request.session, conversation_memory)

        # Update session info
        await chat_config.update_session_info(
            request.session, tool_used, request.prompt_mode
        )

        # Get session info for response
        session_info = (
            await chat_config.redis_client.hgetall(f"session:{request.session}")
            if chat_config.redis_client
            else {}
        )
        message_count = int(session_info.get("message_count", "1"))

        # Prepare Response with Usage Metadata
        # El callback manager ha capturado los tokens de todas las llamadas (extracción + chat principal)
        usage_metadata = {
            "prompt_tokens": (
                chat_config.token_counter.prompt_llm_token_count
                if chat_config.token_counter
                else 0
            ),
            "completion_tokens": (
                chat_config.token_counter.completion_llm_token_count
                if chat_config.token_counter
                else 0
            ),
            "total_tokens": (
                chat_config.token_counter.total_llm_token_count
                if chat_config.token_counter
                else 0
            ),
        }

        # Resetear contadores para la siguiente petición
        if chat_config.token_counter:
            chat_config.token_counter.reset_counts()

        return ChatResponse(
            status=ResponseStatus.SUCCESS,
            data=response_data,
            message="Chat processed successfully",
            session_id=request.session,
            timestamp=datetime.now(),
            provider=chat_config.provider_manager.current_provider,
            tool_used=tool_used,
            language_detected=detected_language,
            conversation_count=message_count,
            prompt_mode_used=request.prompt_mode,
            usage=usage_metadata,
        )

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return ChatResponse(
            status=ResponseStatus.ERROR,
            data={"error": str(e)},
            message=f"Chat processing failed: {str(e)}",
            session_id=request.session,
            timestamp=datetime.now(),
            provider=(
                chat_config.provider_manager.current_provider
                if chat_config.provider_manager
                else "unknown"
            ),
        )


# ============================================================================
# SPECIALIZED TOOL ENDPOINTS
# ============================================================================


@app.post("/tools/fda", response_model=ToolResponse)
async def fda_search_endpoint(request: ToolRequest):
    """Direct FDA drug search endpoint"""
    return await execute_tool_endpoint(ToolType.FDA, request)


@app.post("/tools/pubmed", response_model=ToolResponse)
async def pubmed_search_endpoint(request: ToolRequest):
    """Direct PubMed literature search endpoint"""
    return await execute_tool_endpoint(ToolType.PUBMED, request)


@app.post("/tools/clinical-trials", response_model=ToolResponse)
async def clinical_trials_endpoint(request: ToolRequest):
    """Direct Clinical Trials search endpoint"""
    return await execute_tool_endpoint(ToolType.CLINICAL_TRIALS, request)


@app.post("/tools/icd10", response_model=ToolResponse)
async def icd10_search_endpoint(request: ToolRequest):
    """Direct ICD-10 codes search endpoint"""
    return await execute_tool_endpoint(ToolType.ICD10, request)


@app.post("/tools/scraping", response_model=ToolResponse)
async def web_scraping_endpoint(request: ToolRequest):
    """Direct web scraping endpoint"""
    # For scraping, query should be a URL
    return await execute_tool_endpoint(ToolType.SCRAPING, request)


# ============================================================================
# TOOL EXECUTION HELPERS
# ============================================================================


async def execute_tool_endpoint(
    tool_type: ToolType, request: ToolRequest
) -> ToolResponse:
    """Execute tool endpoint with standardized response"""
    try:
        # Execute tool search
        tool_result = await execute_tool_search(
            tool_type, request.query, request.max_results
        )

        if not tool_result.success:
            return ToolResponse(
                status=ResponseStatus.ERROR,
                data={"error": tool_result.error_message},
                message=f"{tool_type.value} search failed",
                session_id=request.session,
                timestamp=datetime.now(),
                tool_used=tool_type,
                error_details={"query": request.query},
            )

        response_data = {
            "query": request.query,
            "results": tool_result.processed_result,
        }

        # Format with LLM if requested
        if request.format_response and tool_result.processed_result:
            try:
                formatted_result = await format_tool_response_with_llm(
                    tool_result, request.query, request.language
                )
                response_data["formatted_results"] = formatted_result
            except Exception as e:
                logger.warning(f"LLM formatting failed: {e}")
                response_data["formatted_results"] = tool_result.processed_result

        return ToolResponse(
            status=ResponseStatus.SUCCESS,
            data=response_data,
            message=f"{tool_type.value} search completed successfully",
            session_id=request.session,
            timestamp=datetime.now(),
            tool_used=tool_type,
            raw_data=tool_result.raw_result,
            formatted_data=response_data.get("formatted_results"),
            search_term=request.query,
            results_count=(
                tool_result.metadata.get("results_count", 0)
                if tool_result.metadata
                else 0
            ),
        )

    except Exception as e:
        logger.error(f"Tool endpoint error ({tool_type.value}): {e}")
        return ToolResponse(
            status=ResponseStatus.ERROR,
            data={"error": str(e)},
            message=f"{tool_type.value} search failed",
            session_id=request.session,
            timestamp=datetime.now(),
            tool_used=tool_type,
        )


async def execute_tool_search(tool_type: ToolType, query: str, max_results: int = 3):
    """Execute search on specific medical tool with normalization and cache (Punto 3)"""
    try:
        # 1. Verificar cache de normalización
        cache_key = f"{tool_type.value}_{query.lower()}"
        if cache_key in chat_config.tool_extraction_cache:
            normalized_query = chat_config.tool_extraction_cache[cache_key]
            logger.debug(f"Cache hit para normalización: {query} -> {normalized_query}")
        else:
            # 2. Normalizar término usando LLM
            normalized_query = await extract_medical_term(query, tool_type)
            chat_config.tool_extraction_cache[cache_key] = normalized_query
            logger.info(
                f"Tool {tool_type.value}: Original '{query}' -> Normalizado '{normalized_query}'"
            )

        medical_tools = chat_config.medical_tools

        if tool_type == ToolType.FDA:
            return await medical_tools.search_fda_drug(normalized_query, max_results)
        elif tool_type == ToolType.PUBMED:
            return await medical_tools.search_pubmed(normalized_query, max_results)
        elif tool_type == ToolType.CLINICAL_TRIALS:
            return await medical_tools.search_clinical_trials(
                normalized_query, max_results
            )
        elif tool_type == ToolType.ICD10:
            return await medical_tools.search_icd10(normalized_query, max_results)
        elif tool_type == ToolType.SCRAPING:
            # Para scraping, separar URL del término de búsqueda
            if "http" in normalized_query:
                return await medical_tools.scrape_medical_site(normalized_query, None)
            else:
                return await medical_tools.scrape_medical_site(
                    "https://www.mayoclinic.org", normalized_query
                )
        else:
            raise ValueError(f"Unknown tool type: {tool_type}")

    except Exception as e:
        logger.error(f"Tool search error: {e}")
        from models import ToolResult

        return ToolResult(
            success=False, tool_name=tool_type, query=query, error_message=str(e)
        )


import re


async def extract_medical_term(message: str, tool_type: ToolType) -> str:
    """
    Extraer término médico leyendo extraction_prompts del YAML directamente
    """
    try:
        # Leer el YAML directamente
        with open("prompts.yml", "r", encoding="utf-8") as file:
            yaml_data = yaml.safe_load(file)

        # Obtener prompt específico
        tool_name = tool_type.value
        if (
            "extraction_prompts" in yaml_data
            and tool_name in yaml_data["extraction_prompts"]
        ):
            extraction_template = yaml_data["extraction_prompts"][tool_name][
                "system_prompt"
            ]
            prompt = extraction_template.format(message=message)
        else:
            # Fallback
            prompt = f"Extract medical term from: {message}"

        # Usar LLM com um system message extremamente rígido
        from llama_index.core import Settings
        from llama_index.core.llms import ChatMessage

        system_msg = "You are a clinical parser. You only output ONE term. If the user mentions a brand name, output the generic name. If you cannot find one, output the main medical entity. NEVER explain. NEVER use full sentences."
        user_msg = f"GENERIC_NAME_OF: {message}"

        messages = [
            ChatMessage(role="system", content=system_msg),
            ChatMessage(role="user", content=user_msg),
        ]

        response = await asyncio.to_thread(Settings.llm.chat, messages)
        raw_output = str(response.message.content).strip()
        logger.debug(f"Raw LLM extraction output: '{raw_output}'")

        # Limpeza final de precaução
        extracted_term = raw_output.split(":")[-1].strip(" .\"'")

        # Se contiver 'sorry' ou 'cannot' ou parece uma frase longa, usar heurística
        if (
            any(
                word in extracted_term.lower()
                for word in ["sorry", "not", "unable", "assistant"]
            )
            or len(extracted_term.split()) > 3
        ):
            logger.warning(
                f"LLM refusal or chatty output detected. Falling back to heuristic."
            )
            # Heurística: Fármacos costumam começar com Maiúscula
            match = re.findall(r"[A-Z][A-Za-z0-9]+", message)
            if match:
                # Filtrar siglas conhecidas se houver mais de um match
                extracted_term = (
                    [m for m in match if m not in ["FDA", "HIS", "ICD"]][0]
                    if any(m not in ["FDA", "HIS", "ICD"] for m in match)
                    else match[0]
                )
            else:
                extracted_term = message.replace("?", "").split()[-1]

        logger.info(f"Final extracted term: '{extracted_term}' (Raw: '{raw_output}')")
        return extracted_term

    except Exception as e:
        logger.error(f"Error in LLM term extraction: {e}")
        return message.replace("¿", "").replace("?", "").strip()[:50]


# ============================================================================
# async def extract_medical_term(message: str, tool_type: ToolType) -> str:
#    """
#    Extraer término médico relevante del mensaje, limpiando signos de puntuación
#    y palabras irrelevantes para búsqueda en herramientas médicas
#    """
#    try:
#        # 1. Convertir a minúsculas y limpiar
#        message_clean = message.lower().strip()
#
#        # 2. Remover signos de puntuación y caracteres especiales
#        # Mantener solo letras, números, espacios y algunos caracteres especiales médicos
#        message_clean = re.sub(r'[¿?¡!.,;:()\[\]{}"\'-]', ' ', message_clean)
#
#        # 3. Remover palabras comunes (stop words) en español e inglés
#        stop_words = [
#            # Español
#            'que', 'qué', 'es', 'son', 'está', 'están', 'para', 'sirve', 'sirven',
#            'sobre', 'información', 'dime', 'cuéntame', 'explica', 'explicar',
#            'quiero', 'necesito', 'saber', 'conocer', 'ayuda', 'ayúdame',
#            'cómo', 'cuándo', 'dónde', 'por', 'favor', 'gracias', 'hola',
#            'la', 'el', 'los', 'las', 'un', 'una', 'unos', 'unas',
#            'me', 'te', 'se', 'nos', 'le', 'les', 'lo', 'los', 'la', 'las',
#            'de', 'del', 'con', 'sin', 'en', 'por', 'para', 'desde', 'hasta',
#            'puede', 'pueden', 'puedo', 'podemos', 'tiene', 'tienen', 'tengo',
#            # Inglés
#            'what', 'is', 'are', 'for', 'about', 'tell', 'me', 'how', 'when',
#            'where', 'help', 'please', 'thanks', 'hello', 'the', 'a', 'an',
#            'and', 'or', 'but', 'with', 'without', 'can', 'could', 'would',
#            'should', 'will', 'have', 'has', 'had', 'do', 'does', 'did'
#        ]
#
#        # 4. Dividir en palabras y filtrar
#        words = message_clean.split()
#        filtered_words = []
#
#        for word in words:
#            # Limpiar espacios extra de cada palabra
#            word = word.strip()
#            # Filtrar palabras muy cortas (menos de 3 caracteres) y stop words
#            if len(word) >= 3 and word not in stop_words:
#                filtered_words.append(word)
#
#        # 5. Lógica específica por tipo de herramienta
#        if tool_type == ToolType.FDA:
#            # Para FDA, priorizar términos que parezcan nombres de medicamentos
#            drug_keywords = [
#                # Medicamentos comunes en español
#                'aspirina', 'ibuprofeno', 'paracetamol', 'diclofenaco', 'naproxeno',
#                'omeprazol', 'ranitidina', 'loratadina', 'cetirizina', 'dipirona',
#                'acetaminofén', 'ketoprofeno', 'piroxicam', 'meloxicam',
#                # Medicamentos comunes en inglés
#                'aspirin', 'ibuprofen', 'acetaminophen', 'diclofenac', 'naproxen',
#                'omeprazole', 'ranitidine', 'loratadine', 'cetirizine', 'ketorolac',
#                'ketoprofen', 'piroxicam', 'meloxicam', 'tramadol', 'codeine'
#            ]
#
#            # Buscar coincidencias directas con medicamentos conocidos
#            for word in filtered_words:
#                for drug in drug_keywords:
#                    if drug in word or word in drug:
#                        return drug  # Devolver el nombre conocido del medicamento
#
#            # Si no encuentra coincidencias directas, buscar palabras que terminen en sufijos médicos
#            medical_suffixes = ['ina', 'eno', 'ol', 'ona', 'ato', 'ide', 'ine', 'ate']
#            for word in filtered_words:
#                if any(word.endswith(suffix) for suffix in medical_suffixes):
#                    return word
#
#        elif tool_type == ToolType.PUBMED:
#            # Para PubMed, mantener términos médicos/científicos más generales
#            medical_terms = [
#                'diabetes', 'hipertension', 'cancer', 'carcinoma', 'tumor',
#                'cardiovascular', 'neurologico', 'psiquiatrico', 'pediatrico',
#                'geriatrico', 'oncologia', 'cardiologia', 'neurologia'
#            ]
#
#            for word in filtered_words:
#                if word in medical_terms or len(word) > 6:  # Términos largos suelen ser médicos
#                    return word
#
#        elif tool_type == ToolType.ICD10:
#            # Para ICD-10, buscar síntomas o condiciones médicas
#            condition_keywords = [
#                'dolor', 'fiebre', 'tos', 'cefalea', 'mareo', 'nausea',
#                'diarrea', 'estreñimiento', 'fatiga', 'insomnio',
#                'pain', 'fever', 'cough', 'headache', 'nausea', 'diarrhea'
#            ]
#
#            for word in filtered_words:
#                if word in condition_keywords:
#                    return word
#
#        elif tool_type == ToolType.CLINICAL_TRIALS:
#            # Para ensayos clínicos, similar a PubMed pero más específico
#            pass
#
#        # 6. Fallback: devolver la primera palabra relevante encontrada
#        if filtered_words:
#            # Priorizar palabras más largas (suelen ser más específicas)
#            filtered_words.sort(key=len, reverse=True)
#            return filtered_words[0]
#
#        # 7. Último fallback: limpiar el mensaje original y devolver
#        # Remover solo signos de puntuación pero mantener palabras
#        fallback = re.sub(r'[¿?¡!.,;:()\[\]{}"\'-]+', '', message.lower().strip())
#        fallback_words = [w.strip() for w in fallback.split() if len(w.strip()) >= 3]
#
#        if fallback_words:
#            return fallback_words[0]
#
#        # Si todo falla, devolver el mensaje original limpio
#        return re.sub(r'[¿?¡!.,;:()]+', '', message.strip())
#
#    except Exception as e:
#        logger.error(f"Error in extract_medical_term: {e}")
#        # En caso de error, devolver mensaje limpio
#        return re.sub(r'[¿?¡!.,;:()]+', '', message.strip())


async def format_tool_response_with_llm(
    tool_result, original_query: str, language: str = "auto"
) -> str:
    """Format tool response using LLM for better presentation"""
    try:
        # Create a temporary chat engine for formatting
        temp_session = f"format_{uuid.uuid4().hex[:8]}"
        chat_engine = await chat_config.get_or_create_chat_engine(
            temp_session, PromptMode.MEDICAL
        )

        formatting_prompt = f"""
        The user asked: "{original_query}"
        
        Raw data from {tool_result.tool_name.value.upper()}:
        {tool_result.processed_result}
        
        Please format this information in a professional, readable way using markdown.
        Respond in {'Spanish' if language == 'es' else 'English'}.
        Include appropriate medical disclaimers.
        """

        response = await asyncio.to_thread(chat_engine.chat, formatting_prompt)
        return str(response)

    except Exception as e:
        logger.error(f"LLM formatting error: {e}")
        return tool_result.processed_result


# ============================================================================
# PROVIDER MANAGEMENT ENDPOINTS
# ============================================================================


@app.get("/providers", response_model=StandardResponse)
async def list_providers():
    """List all available LLM providers"""
    try:
        providers = []
        for provider_name in chat_config.provider_manager.get_available_providers():
            info = chat_config.provider_manager.get_provider_info(provider_name)
            info["is_current"] = (
                provider_name == chat_config.provider_manager.current_provider
            )
            providers.append(info)

        return create_success_response(
            data={"providers": providers}, message="Providers listed successfully"
        )

    except Exception as e:
        return create_error_response(f"Error listing providers: {str(e)}")


@app.get("/providers/current", response_model=StandardResponse)
async def get_current_provider():
    """Get current active provider information"""
    try:
        provider_info = chat_config.provider_manager.get_provider_info()
        return create_success_response(
            data={"current_provider": provider_info},
            message="Current provider retrieved successfully",
        )
    except Exception as e:
        return create_error_response(f"Error getting current provider: {str(e)}")


# ============================================================================
# PROMPT MANAGEMENT ENDPOINTS
# ============================================================================


@app.get("/prompts", response_model=StandardResponse)
async def list_prompts():
    """List all available prompt modes"""
    try:
        prompts_info = await chat_config.prompt_manager.get_prompts_info()
        return create_success_response(
            data={"prompts": prompts_info},
            message="Prompts information retrieved successfully",
        )
    except Exception as e:
        return create_error_response(f"Error getting prompts info: {str(e)}")


@app.post("/prompts/reload", response_model=StandardResponse)
async def reload_prompts():
    """Hot reload prompts from YAML file"""
    try:
        success = await chat_config.prompt_manager.reload_prompts()
        if success:
            # Clear chat engines to use new prompts
            chat_config.chat_engines.clear()
            return create_success_response(
                data={"reloaded": True}, message="Prompts reloaded successfully"
            )
        else:
            return create_error_response("Failed to reload prompts")
    except Exception as e:
        return create_error_response(f"Error reloading prompts: {str(e)}")


# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================================


@app.get("/sessions/{session_id}", response_model=StandardResponse)
async def get_session_info(session_id: str):
    """Get detailed session information"""
    try:
        if not chat_config.redis_client:
            return create_error_response("Redis not available")

        session_data = await chat_config.redis_client.hgetall(f"session:{session_id}")

        if not session_data:
            return create_error_response("Session not found", "SESSION_NOT_FOUND")

        # Parse JSON fields
        session_data["tools_used"] = json.loads(session_data.get("tools_used", "[]"))
        session_data["prompt_modes_used"] = json.loads(
            session_data.get("prompt_modes_used", "[]")
        )

        return create_success_response(
            data={"session": session_data},
            message="Session information retrieved successfully",
            session_id=session_id,
        )

    except Exception as e:
        return create_error_response(f"Error getting session info: {str(e)}")


@app.get("/sessions", response_model=StandardResponse)
async def list_active_sessions():
    """List all active sessions"""
    try:
        if not chat_config.redis_client:
            return create_error_response("Redis not available")

        session_keys = await chat_config.redis_client.keys("session:*")
        sessions = []

        for key in session_keys:
            session_data = await chat_config.redis_client.hgetall(key)
            if session_data:
                session_data["tools_used"] = json.loads(
                    session_data.get("tools_used", "[]")
                )
                session_data["prompt_modes_used"] = json.loads(
                    session_data.get("prompt_modes_used", "[]")
                )
                sessions.append(session_data)

        return create_success_response(
            data={"sessions": sessions, "count": len(sessions)},
            message="Active sessions retrieved successfully",
        )

    except Exception as e:
        return create_error_response(f"Error listing sessions: {str(e)}")


@app.delete("/sessions/{session_id}", response_model=StandardResponse)
async def clear_session(session_id: str):
    """Clear specific session data"""
    try:
        # Remove chat engines
        keys_to_remove = [
            k for k in chat_config.chat_engines.keys() if k.startswith(session_id)
        ]
        for key in keys_to_remove:
            del chat_config.chat_engines[key]

        # Remove from Redis
        if chat_config.redis_client:
            await chat_config.redis_client.delete(f"session:{session_id}")
            await chat_config.redis_client.delete(f"conversation:{session_id}")

        return create_success_response(
            data={"cleared": True},
            message=f"Session {session_id} cleared successfully",
            session_id=session_id,
        )

    except Exception as e:
        return create_error_response(f"Error clearing session: {str(e)}")


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    logger.info(f"WebSocket connected: {session_id}")

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Create ChatRequest from WebSocket data
            chat_request = ChatRequest(
                message=message_data.get("message", ""),
                session=session_id,
                tools=(
                    ToolType(message_data["tools"])
                    if message_data.get("tools")
                    else None
                ),
                prompt_mode=PromptMode(message_data.get("prompt_mode", "medical")),
                language=message_data.get("language", "auto"),
            )

            # Process through unified chat endpoint
            response = await unified_chat_endpoint(chat_request)

            # Send response back through WebSocket
            await websocket.send_text(response.model_dump_json())

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


# ============================================================================
# MAIN APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=7005, reload=True, log_level="info")
