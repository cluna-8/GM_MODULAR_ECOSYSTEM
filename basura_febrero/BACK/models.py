# models.py - Pydantic Models Unificados para Arquitectura Híbrida
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum

# ============================================================================
# ENUMS
# ============================================================================

class ToolType(str, Enum):
    """Herramientas médicas disponibles"""
    FDA = "fda"
    PUBMED = "pubmed" 
    CLINICAL_TRIALS = "clinical_trials"
    ICD10 = "icd10"
    SCRAPING = "scraping"

class PromptMode(str, Enum):
    """Modos de prompts disponibles"""
    MEDICAL = "medical"
    PEDIATRIC = "pediatric"
    EMERGENCY = "emergency"
    PHARMACY = "pharmacy"
    GENERAL = "general"

class ResponseStatus(str, Enum):
    """Estados de respuesta"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"

# ============================================================================
# REQUEST MODELS
# ============================================================================

class ChatRequest(BaseModel):
    """Modelo unificado para el endpoint /chat"""
    message: str = Field(..., description="Mensaje del usuario", min_length=1)
    session: str = Field(..., description="ID de sesión único")
    token: Optional[str] = Field(None, description="Token de usuario (para API Gateway)")
    tools: Optional[ToolType] = Field(None, description="Herramienta específica a usar")
    prompt_mode: Optional[PromptMode] = Field(PromptMode.MEDICAL, description="Modo de prompt")
    language: Optional[str] = Field("auto", description="Idioma preferido (auto, es, en)")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexto adicional")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "¿Qué es la aspirina?",
                "session": "user-123-session-456", 
                "tools": "fda",
                "prompt_mode": "medical",
                "language": "es"
            }
        }

class ToolRequest(BaseModel):
    """Modelo para endpoints específicos /tools/{name}"""
    query: str = Field(..., description="Consulta para la herramienta", min_length=1)
    session: Optional[str] = Field(None, description="ID de sesión (opcional para tools directos)")
    token: Optional[str] = Field(None, description="Token de usuario")
    max_results: Optional[int] = Field(3, description="Máximo número de resultados", ge=1, le=10)
    format_response: Optional[bool] = Field(True, description="Formatear respuesta con LLM")
    language: Optional[str] = Field("auto", description="Idioma de respuesta")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "aspirin",
                "session": "user-123",
                "max_results": 3,
                "format_response": True,
                "language": "es"
            }
        }

class PromptUpdateRequest(BaseModel):
    """Modelo para actualizar prompts"""
    mode: PromptMode = Field(..., description="Modo de prompt a actualizar")
    system_prompt: str = Field(..., description="Nuevo prompt del sistema")
    temperature: Optional[float] = Field(0.1, description="Temperatura del LLM", ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(1000, description="Máximo tokens", ge=100, le=4000)
    
class SessionRequest(BaseModel):
    """Modelo para operaciones de sesión"""
    session_id: str = Field(..., description="ID de sesión")
    action: str = Field(..., description="Acción a realizar (clear, get, list)")

# ============================================================================
# RESPONSE MODELS  
# ============================================================================

class StandardResponse(BaseModel):
    """Respuesta estándar unificada para toda la API"""
    status: ResponseStatus = Field(..., description="Estado de la respuesta")
    data: Optional[Dict[str, Any]] = Field(None, description="Datos de respuesta")
    message: Optional[str] = Field(None, description="Mensaje descriptivo")
    session_id: Optional[str] = Field(None, description="ID de sesión")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp de respuesta")
    provider: Optional[str] = Field(None, description="Proveedor LLM usado")
    tool_used: Optional[ToolType] = Field(None, description="Herramienta usada")
    language_detected: Optional[str] = Field(None, description="Idioma detectado")
    tokens_used: Optional[int] = Field(None, description="Tokens consumidos")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "data": {
                    "response": "La aspirina es un medicamento...",
                    "context_saved": True
                },
                "message": "Consulta procesada exitosamente",
                "session_id": "user-123",
                "provider": "openai",
                "tool_used": "fda",
                "language_detected": "es"
            }
        }

class ChatResponse(StandardResponse):
    """Respuesta específica para chat"""
    conversation_count: Optional[int] = Field(None, description="Número de mensajes en conversación")
    prompt_mode_used: Optional[PromptMode] = Field(None, description="Modo de prompt usado")

class ToolResponse(StandardResponse):
    """Respuesta específica para herramientas"""
    raw_data: Optional[str] = Field(None, description="Datos crudos de la herramienta")
    formatted_data: Optional[str] = Field(None, description="Datos formateados por LLM")
    search_term: Optional[str] = Field(None, description="Término de búsqueda procesado")
    results_count: Optional[int] = Field(None, description="Número de resultados encontrados")

class ErrorResponse(StandardResponse):
    """Respuesta de error estandarizada"""
    error_code: Optional[str] = Field(None, description="Código de error específico")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detalles adicionales del error")
    
    def __init__(self, **data):
        super().__init__(**data)
        self.status = ResponseStatus.ERROR

# ============================================================================
# INTERNAL MODELS (para uso interno de la API)
# ============================================================================

class PromptConfig(BaseModel):
    """Configuración de prompt desde YAML"""
    system_prompt: str = Field(..., description="Prompt del sistema")
    temperature: float = Field(0.1, description="Temperatura del LLM")
    max_tokens: int = Field(1000, description="Máximo tokens")
    description: Optional[str] = Field(None, description="Descripción del prompt")
    
class SessionInfo(BaseModel):
    """Información de sesión para Redis"""
    session_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int = 0
    provider: str
    tools_used: List[ToolType] = []
    prompt_modes_used: List[PromptMode] = []
    language: str = "auto"
    
class ToolResult(BaseModel):
    """Resultado interno de herramientas MCP"""
    success: bool
    tool_name: ToolType
    query: str
    raw_result: Optional[str] = None
    processed_result: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ConversationMemory(BaseModel):
    """Estructura para guardar en memoria de conversación"""
    user_message: str
    tool_used: Optional[ToolType] = None
    raw_tool_data: Optional[str] = None
    assistant_response: str
    timestamp: datetime
    prompt_mode: PromptMode
    metadata: Optional[Dict[str, Any]] = None

# ============================================================================
# VALIDATION MODELS
# ============================================================================

class HealthCheck(BaseModel):
    """Modelo para health check"""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.now)
    services: Dict[str, Any]
    version: str = "2.0.0"

class ProviderInfo(BaseModel):
    """Información de proveedor LLM"""
    provider: str
    model: str
    embedding_model: Optional[str] = None
    status: str
    is_current: bool = False

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_success_response(
    data: Dict[str, Any],
    message: str = "Success",
    session_id: str = None,
    **kwargs
) -> StandardResponse:
    """Helper para crear respuestas exitosas"""
    return StandardResponse(
        status=ResponseStatus.SUCCESS,
        data=data,
        message=message,
        session_id=session_id,
        **kwargs
    )

def create_error_response(
    message: str,
    error_code: str = None,
    session_id: str = None,
    **kwargs
) -> ErrorResponse:
    """Helper para crear respuestas de error"""
    return ErrorResponse(
        message=message,
        error_code=error_code,
        session_id=session_id,
        **kwargs
    )

# ============================================================================
# MODEL REGISTRY (para documentación automática)
# ============================================================================

REQUEST_MODELS = {
    "chat": ChatRequest,
    "tool": ToolRequest,
    "prompt_update": PromptUpdateRequest,
    "session": SessionRequest
}

RESPONSE_MODELS = {
    "standard": StandardResponse,
    "chat": ChatResponse,
    "tool": ToolResponse,
    "error": ErrorResponse,
    "health": HealthCheck
}