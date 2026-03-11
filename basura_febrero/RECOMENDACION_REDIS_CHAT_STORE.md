# Recomendación Técnica: Persistencia de Memoria Conversacional

**Fecha**: 2026-02-11  
**Objetivo**: Implementar persistencia robusta y eficiente para memoria conversacional  
**Basado en**: LlamaIndex Best Practices + Arquitectura Actual

---

## 🎯 Técnica Recomendada: **RedisChatStore Nativo de LlamaIndex**

### **Por qué esta solución**

✅ **Ventajas**:
1. **Nativa de LlamaIndex**: Integración oficial y mantenida
2. **Automática**: No requiere serialización/deserialización manual
3. **Escalable**: Diseñada para múltiples sesiones concurrentes
4. **TTL integrado**: Gestión automática de expiración
5. **Compatible**: Funciona directamente con `SimpleChatEngine`
6. **Probada**: Solución estándar en producción

❌ **Tu implementación actual** (manual):
- Guardas `ConversationMemory` como JSON en Redis
- Requiere reconstrucción manual del `ChatMemoryBuffer`
- Propenso a errores de sincronización
- Más código de mantenimiento

---

## 📊 Comparación de Enfoques

### **Opción 1: RedisChatStore (RECOMENDADA)**

```python
from llama_index.storage.chat_store import RedisChatStore
from llama_index.core.memory import ChatMemoryBuffer

# Inicialización (una vez)
chat_store = RedisChatStore(
    redis_url="redis://redis-general:6379/0",
    ttl=604800  # 7 días
)

# Crear memoria con persistencia automática
memory = ChatMemoryBuffer.from_defaults(
    chat_store=chat_store,
    chat_store_key=f"chat_{session_id}",  # Clave única por sesión
    token_limit=3000
)

# Crear engine (la memoria se persiste automáticamente)
chat_engine = SimpleChatEngine.from_defaults(
    llm=Settings.llm,
    memory=memory,
    system_prompt=system_prompt
)
```

**Flujo automático**:
```
Usuario: "Mi nombre es Juan"
    ↓
chat_engine.chat() → Actualiza memory
    ↓
memory → Guarda automáticamente en Redis (RedisChatStore)
    ↓
Reinicio del contenedor
    ↓
Nueva memoria con mismo chat_store_key → Carga automáticamente desde Redis
```

---

### **Opción 2: Implementación Manual (ACTUAL)**

```python
# Guardar (manual)
memory_data = ConversationMemory(...).model_dump_json()
await redis_client.lpush(f"conversation:{session_id}", memory_data)

# Cargar (manual - FALTA IMPLEMENTAR)
messages = await redis_client.lrange(f"conversation:{session_id}", 0, -1)
for msg_json in reversed(messages):
    msg = json.loads(msg_json)
    # Reconstruir ChatMemoryBuffer manualmente
    memory.put(ChatMessage(role="user", content=msg["user_message"]))
    memory.put(ChatMessage(role="assistant", content=msg["assistant_response"]))
```

**Problemas**:
- ❌ Requiere código de serialización/deserialización
- ❌ Propenso a errores de formato
- ❌ Más difícil de mantener
- ❌ No aprovecha optimizaciones de LlamaIndex

---

## 🚀 Plan de Migración Recomendado

### **Fase 1: Instalación (5 min)**

```bash
pip install llama-index-storage-chat-store-redis
```

**Agregar a `requirements.txt`**:
```
llama-index-storage-chat-store-redis>=0.1.0
```

---

### **Fase 2: Modificar HybridChatConfig (30 min)**

#### **2.1 Inicialización (líneas 134-143)**

**ANTES**:
```python
def __init__(self):
    self.provider_manager: Optional[ProviderManager] = None
    self.redis_client: Optional[redis.Redis] = None
    self.medical_tools: Optional[MedicalTools] = None
    self.prompt_manager: Optional[PromptManager] = None
    self.token_counter: Optional[TokenCountingHandler] = None
    self.chat_engines: Dict[str, SimpleChatEngine] = {}
    self.tool_extraction_cache: Dict[str, str] = {}
    self.auditor: Optional[MedicalAuditorClient] = None
    self.initialized = False
```

**DESPUÉS**:
```python
from llama_index.storage.chat_store import RedisChatStore

def __init__(self):
    self.provider_manager: Optional[ProviderManager] = None
    self.redis_client: Optional[redis.Redis] = None
    self.chat_store: Optional[RedisChatStore] = None  # NUEVO
    self.medical_tools: Optional[MedicalTools] = None
    self.prompt_manager: Optional[PromptManager] = None
    self.token_counter: Optional[TokenCountingHandler] = None
    self.chat_engines: Dict[str, SimpleChatEngine] = {}
    self.tool_extraction_cache: Dict[str, str] = {}
    self.auditor: Optional[MedicalAuditorClient] = None
    self.initialized = False
```

#### **2.2 Inicializar RedisChatStore (líneas 168-177)**

**ANTES**:
```python
# Initialize Redis
redis_url = os.getenv("REDIS_URL", "redis://redis-general:6379/0")
self.redis_client = redis.from_url(
    redis_url,
    encoding="utf-8",
    decode_responses=True,
)
logger.info("✅ Redis connection established")
```

**DESPUÉS**:
```python
# Initialize Redis
redis_url = os.getenv("REDIS_URL", "redis://redis-general:6379/0")
self.redis_client = redis.from_url(
    redis_url,
    encoding="utf-8",
    decode_responses=True,
)
logger.info("✅ Redis connection established")

# Initialize RedisChatStore for conversation persistence
self.chat_store = RedisChatStore(
    redis_url=redis_url,
    ttl=604800  # 7 días
)
logger.info("✅ RedisChatStore initialized for conversation persistence")
```

#### **2.3 Modificar get_or_create_chat_engine() (líneas 200-265)**

**ANTES**:
```python
async def get_or_create_chat_engine(
    self,
    session_id: str,
    prompt_mode: PromptMode,
    custom_system_prompt: Optional[str] = None,
) -> SimpleChatEngine:
    engine_key = f"{session_id}_{prompt_mode.value}_{self.provider_manager.current_provider}"
    
    if engine_key not in self.chat_engines or custom_system_prompt:
        try:
            # Obtener la memoria si ya existía el motor
            existing_memory = None
            if engine_key in self.chat_engines:
                engine = self.chat_engines[engine_key]
                existing_memory = getattr(engine, "memory", getattr(engine, "_memory", None))
            
            # Get prompt configuration
            prompt_config = await self.prompt_manager.get_prompt(prompt_mode)
            system_prompt = custom_system_prompt if custom_system_prompt else prompt_config.system_prompt
            
            # Create or reuse memory buffer
            if existing_memory:
                memory = existing_memory
            else:
                try:
                    memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
                except Exception:
                    memory = ChatMemoryBuffer.from_defaults()
            
            # Create chat engine
            chat_engine = SimpleChatEngine.from_defaults(
                llm=Settings.llm,
                memory=memory,
                system_prompt=system_prompt,
            )
            
            self.chat_engines[engine_key] = chat_engine
            logger.debug(f"Created/Updated chat engine: {engine_key}")
        
        except Exception as e:
            logger.error(f"Error creating chat engine: {e}")
            raise
    
    return self.chat_engines[engine_key]
```

**DESPUÉS**:
```python
async def get_or_create_chat_engine(
    self,
    session_id: str,
    prompt_mode: PromptMode,
    custom_system_prompt: Optional[str] = None,
) -> SimpleChatEngine:
    """Get or create chat engine with persistent memory via RedisChatStore"""
    engine_key = f"{session_id}_{prompt_mode.value}_{self.provider_manager.current_provider}"
    
    if engine_key not in self.chat_engines or custom_system_prompt:
        try:
            # Get prompt configuration
            prompt_config = await self.prompt_manager.get_prompt(prompt_mode)
            system_prompt = custom_system_prompt if custom_system_prompt else prompt_config.system_prompt
            
            # Create memory with RedisChatStore for automatic persistence
            # La clave única es el session_id (sin prompt_mode ni provider)
            # para mantener continuidad conversacional incluso si cambia el modo
            chat_store_key = f"chat_{session_id}"
            
            try:
                memory = ChatMemoryBuffer.from_defaults(
                    chat_store=self.chat_store,
                    chat_store_key=chat_store_key,
                    token_limit=3000
                )
                logger.debug(f"Created memory with RedisChatStore for {chat_store_key}")
            except Exception as e:
                logger.warning(f"Failed to create memory with chat store: {e}, using default")
                memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
            
            # Create chat engine with persistent memory
            chat_engine = SimpleChatEngine.from_defaults(
                llm=Settings.llm,
                memory=memory,
                system_prompt=system_prompt,
            )
            
            self.chat_engines[engine_key] = chat_engine
            logger.info(f"Created/Updated chat engine: {engine_key} with persistent memory")
        
        except Exception as e:
            logger.error(f"Error creating chat engine: {e}")
            raise
    
    return self.chat_engines[engine_key]
```

---

### **Fase 3: Eliminar Código Obsoleto (15 min)**

#### **3.1 save_conversation_memory() - DEPRECAR**

**Líneas 309-333** - Ya no es necesario porque `RedisChatStore` guarda automáticamente.

**Opción A**: Eliminar completamente  
**Opción B**: Mantener para logging adicional (recomendado para auditoría)

```python
async def save_conversation_memory(
    self, session_id: str, memory: ConversationMemory
) -> bool:
    """
    DEPRECATED: RedisChatStore now handles persistence automatically.
    Kept for additional audit logging only.
    """
    if not self.redis_client:
        return False
    
    try:
        # Guardar en formato legacy para auditoría/RLHF
        audit_key = f"audit:conversation:{session_id}"
        memory_data = memory.model_dump_json()
        await self.redis_client.lpush(audit_key, memory_data)
        await self.redis_client.ltrim(audit_key, 0, 49)
        await self.redis_client.expire(audit_key, 604800)
        
        logger.debug(f"Saved audit log for {session_id}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving audit log: {e}")
        return False
```

#### **3.2 Actualizar unified_chat_endpoint() (líneas 828-838)**

**ANTES**:
```python
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
```

**DESPUÉS** (opcional, solo para auditoría):
```python
# Save audit log (RedisChatStore already persisted the conversation)
conversation_memory = ConversationMemory(
    user_message=request.message,
    tool_used=tool_used,
    raw_tool_data=raw_tool_data,
    assistant_response=response_data["response"],
    timestamp=datetime.now(),
    prompt_mode=request.prompt_mode,
    metadata={"language": detected_language, "session": request.session},
)
# Guardar en clave separada para auditoría/RLHF
await chat_config.save_conversation_memory(request.session, conversation_memory)
```

---

## 🔍 Estructura en Redis (DESPUÉS)

### **Con RedisChatStore**:

```
# Conversación persistente (gestionada por RedisChatStore)
Key: chat_test_session_001
Type: HASH
Fields:
  messages: [serialized ChatMessage objects]
  
# Auditoría adicional (opcional, tu implementación actual)
Key: audit:conversation:test_session_001
Type: LIST
Value: [JSON objects con metadata extendida]
```

---

## ✅ Ventajas de esta Migración

| Aspecto | Antes (Manual) | Después (RedisChatStore) |
|---------|----------------|--------------------------|
| **Persistencia** | Manual, propenso a errores | Automática, robusta |
| **Código** | ~50 líneas custom | ~10 líneas (nativo) |
| **Mantenimiento** | Alto (custom logic) | Bajo (LlamaIndex mantiene) |
| **Sincronización** | Manual (puede fallar) | Automática (garantizada) |
| **Compatibilidad** | Depende de tu implementación | Compatible con futuras versiones |
| **Testing** | Requiere tests custom | Tests incluidos en LlamaIndex |
| **TTL** | Manual | Integrado |
| **Escalabilidad** | Limitada | Optimizada para producción |

---

## 🧪 Plan de Testing

### **Test 1: Persistencia Básica**
```bash
# Consulta 1
curl -X POST http://localhost:8000/medical/chat \
  -H "Authorization: Bearer hcg_maestro_123" \
  -d '{"promptData": "Mi nombre es Juan", "sessionId": "test_redis_store", "IAType": "medical"}'

# Reiniciar contenedor
docker restart gm-general-chat

# Consulta 2 (debe recordar)
curl -X POST http://localhost:8000/medical/chat \
  -H "Authorization: Bearer hcg_maestro_123" \
  -d '{"promptData": "¿Cuál es mi nombre?", "sessionId": "test_redis_store", "IAType": "medical"}'

# Esperado: "Tu nombre es Juan"
```

### **Test 2: Verificar en Redis**
```bash
docker exec redis-general redis-cli

# Ver claves de chat
KEYS chat_*

# Ver contenido
HGETALL chat_test_redis_store

# Verificar TTL
TTL chat_test_redis_store
# Esperado: ~604800 (7 días en segundos)
```

### **Test 3: Múltiples Sesiones**
```bash
# Sesión A
curl ... -d '{"promptData": "Soy diabético", "sessionId": "session_a", ...}'

# Sesión B
curl ... -d '{"promptData": "Tengo hipertensión", "sessionId": "session_b", ...}'

# Verificar que no interfieren
curl ... -d '{"promptData": "¿Qué condición tengo?", "sessionId": "session_a", ...}'
# Esperado: "diabetes" (NO hipertensión)
```

---

## 📋 Checklist de Implementación

- [ ] Instalar `llama-index-storage-chat-store-redis`
- [ ] Agregar import de `RedisChatStore`
- [ ] Inicializar `self.chat_store` en `__init__()`
- [ ] Modificar `get_or_create_chat_engine()` para usar `RedisChatStore`
- [ ] (Opcional) Deprecar `save_conversation_memory()` o mantener para auditoría
- [ ] Actualizar `unified_chat_endpoint()` si es necesario
- [ ] Testing local completo
- [ ] Commit y push
- [ ] Despliegue en producción
- [ ] Validación con `test_production.sh`

---

## 🎯 Resumen Ejecutivo

**Recomendación**: Migrar a `RedisChatStore` nativo de LlamaIndex

**Razón**: 
- ✅ Solución oficial y mantenida
- ✅ Automática (menos código, menos errores)
- ✅ Escalable y probada en producción
- ✅ Compatible con futuras versiones

**Esfuerzo**: 1 hora de implementación + 30 min de testing

**Riesgo**: Bajo (fallback a memoria nueva si falla)

**Impacto**: Alto (funcionalidad crítica para UX)

**Alternativa**: Implementar carga manual desde tu estructura actual (más trabajo, más mantenimiento)
