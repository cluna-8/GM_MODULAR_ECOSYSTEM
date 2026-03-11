# Análisis Completo: gm_general_chat - Gestión de Sesiones

**Fecha**: 2026-02-11  
**Archivo Analizado**: `SERVICES/gm_general_chat/main.py` (1501 líneas)  
**Enfoque**: Persistencia de memoria conversacional

---

## 📊 Arquitectura General

### **Flujo de Petición**
```
Cliente → Gateway → /chat endpoint (línea 644)
                        ↓
                  unified_chat_endpoint()
                        ↓
            ┌───────────┴───────────┐
            ↓                       ↓
    get_or_create_chat_engine   save_conversation_memory
            ↓                       ↓
    SimpleChatEngine          Redis (conversation:*)
    + ChatMemoryBuffer
```

---

## 🔍 Componentes Clave

### **1. HybridChatConfig (Clase Principal)**

**Ubicación**: Líneas 131-505

**Atributos relevantes para persistencia**:
```python
self.chat_engines: Dict[str, SimpleChatEngine] = {}  # Caché en memoria
self.redis_client: Optional[redis.Redis] = None      # Persistencia
```

**Métodos clave**:
- `get_or_create_chat_engine()` - Líneas 200-265
- `save_conversation_memory()` - Líneas 309-333
- `update_session_info()` - Líneas 335-401

---

### **2. get_or_create_chat_engine() - ANÁLISIS DETALLADO**

**Líneas 200-265**

#### **Clave de Engine**:
```python
engine_key = f"{session_id}_{prompt_mode.value}_{self.provider_manager.current_provider}"
```

**Ejemplo**: `"test_session_medical_openai"`

#### **Lógica Actual**:

```python
# 1. Verificar si existe en caché
if engine_key not in self.chat_engines or custom_system_prompt:
    
    # 2. Intentar recuperar memoria existente (SOLO de caché en memoria)
    existing_memory = None
    if engine_key in self.chat_engines:
        engine = self.chat_engines[engine_key]
        existing_memory = getattr(engine, "memory", getattr(engine, "_memory", None))
    
    # 3. Crear memoria nueva si no existe
    if existing_memory:
        memory = existing_memory
    else:
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
    
    # 4. Crear nuevo engine con la memoria
    chat_engine = SimpleChatEngine.from_defaults(
        llm=Settings.llm,
        memory=memory,
        system_prompt=system_prompt,
    )
    
    # 5. Guardar en caché
    self.chat_engines[engine_key] = chat_engine
```

#### **🚨 PROBLEMA IDENTIFICADO**:

**La memoria SOLO se recupera del caché en memoria (`self.chat_engines`), NO de Redis.**

**Consecuencia**:
- Si el contenedor se reinicia → `self.chat_engines = {}` → Se pierde toda la memoria
- Si pasa tiempo sin actividad → El engine podría ser eliminado del caché → Nueva conversación sin contexto

---

### **3. save_conversation_memory() - ANÁLISIS DETALLADO**

**Líneas 309-333**

#### **Implementación Actual**:

```python
async def save_conversation_memory(
    self, session_id: str, memory: ConversationMemory
) -> bool:
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
```

#### **✅ LO QUE FUNCIONA**:
- Guarda cada mensaje en Redis como JSON
- Usa una lista (`LPUSH`) para mantener orden cronológico
- Limita a 50 mensajes (gestión de memoria)
- TTL de 7 días (604800 segundos)

#### **Estructura en Redis**:
```
Key: conversation:test_session
Type: LIST
Value: [
    '{"user_message": "Hola", "assistant_response": "...", "timestamp": "..."}',
    '{"user_message": "¿Qué es el asma?", "assistant_response": "...", "timestamp": "..."}'
]
```

---

### **4. Endpoint Principal: unified_chat_endpoint()**

**Líneas 644-900**

#### **Flujo de Persistencia**:

```python
# Línea 697: Obtener/crear engine
chat_engine = await chat_config.get_or_create_chat_engine(
    request.session,
    request.prompt_mode,
    custom_system_prompt=system_prompt_filled,
)

# Línea 785: Ejecutar chat (usa memoria interna del engine)
llm_response_obj = await asyncio.to_thread(chat_engine.chat, final_message)

# Línea 829-838: Guardar en Redis DESPUÉS de la respuesta
conversation_memory = ConversationMemory(
    user_message=request.message,
    assistant_response=response_data["response"],
    timestamp=datetime.now(),
    ...
)
await chat_config.save_conversation_memory(request.session, conversation_memory)
```

#### **🔍 OBSERVACIÓN CRÍTICA**:

**Hay DOS sistemas de memoria operando en paralelo**:

1. **ChatMemoryBuffer (LlamaIndex)**: Memoria interna del `SimpleChatEngine`
   - Se usa durante `chat_engine.chat()`
   - Mantiene contexto para la conversación actual
   - **NO se sincroniza con Redis**

2. **Redis (conversation:{session_id})**: Persistencia externa
   - Se guarda DESPUÉS de cada respuesta
   - Formato: `ConversationMemory` (Pydantic model)
   - **NO se carga de vuelta al ChatMemoryBuffer**

---

## 🎯 DIAGNÓSTICO FINAL

### **¿Por qué NO funciona la persistencia?**

#### **Escenario 1: Reinicio del Contenedor**
```
1. Usuario: "Mi nombre es Juan" → Se guarda en Redis ✅
2. Contenedor se reinicia → self.chat_engines = {} ❌
3. Usuario: "¿Cuál es mi nombre?" → Nuevo engine SIN memoria ❌
4. Resultado: "No tengo información sobre tu nombre" ❌
```

#### **Escenario 2: Múltiples Consultas (mismo contenedor)**
```
1. Usuario: "Mi nombre es Juan"
   - ChatMemoryBuffer: ["Mi nombre es Juan", "Hola Juan..."] ✅
   - Redis: [{"user_message": "Mi nombre es Juan", ...}] ✅

2. Usuario: "¿Cuál es mi nombre?"
   - ChatMemoryBuffer: ["Mi nombre es Juan", "Hola Juan...", "¿Cuál es mi nombre?"] ✅
   - Engine reutiliza memoria del caché ✅
   - Resultado: "Tu nombre es Juan" ✅
```

**Conclusión**: Funciona SOLO si el engine permanece en `self.chat_engines`.

---

## 🔧 SOLUCIÓN REQUERIDA

### **Implementar Carga de Memoria desde Redis**

#### **Nueva Función Necesaria**:

```python
async def load_conversation_memory_from_redis(
    self, session_id: str
) -> Optional[ChatMemoryBuffer]:
    """
    Cargar historial de conversación desde Redis y reconstruir ChatMemoryBuffer
    """
    if not self.redis_client:
        return None
    
    try:
        memory_key = f"conversation:{session_id}"
        messages = await self.redis_client.lrange(memory_key, 0, -1)
        
        if not messages:
            logger.debug(f"No conversation history found for {session_id}")
            return None
        
        # Crear buffer de memoria
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
        
        # Cargar mensajes en orden cronológico (Redis LPUSH invierte el orden)
        for msg_json in reversed(messages):
            msg_data = json.loads(msg_json)
            
            # Agregar al buffer usando la API de LlamaIndex
            # NOTA: Verificar documentación de ChatMemoryBuffer para formato correcto
            memory.put(ChatMessage(
                role="user",
                content=msg_data["user_message"]
            ))
            memory.put(ChatMessage(
                role="assistant",
                content=msg_data["assistant_response"]
            ))
        
        logger.info(f"Loaded {len(messages)} messages for session {session_id}")
        return memory
        
    except Exception as e:
        logger.error(f"Error loading conversation memory from Redis: {e}")
        return None
```

#### **Modificación en get_or_create_chat_engine()**:

**Líneas 229-236 (ANTES)**:
```python
# Create or reuse memory buffer
if existing_memory:
    memory = existing_memory
else:
    try:
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
    except Exception:
        memory = ChatMemoryBuffer.from_defaults()
```

**Líneas 229-240 (DESPUÉS)**:
```python
# Create or reuse memory buffer
if existing_memory:
    memory = existing_memory
    logger.debug(f"Reusing in-memory buffer for {engine_key}")
else:
    # NUEVO: Intentar cargar desde Redis primero
    memory = await self.load_conversation_memory_from_redis(session_id)
    
    if memory:
        logger.info(f"Loaded memory from Redis for {session_id}")
    else:
        # Si no hay memoria en Redis, crear nueva
        try:
            memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
            logger.debug(f"Created new memory buffer for {session_id}")
        except Exception:
            memory = ChatMemoryBuffer.from_defaults()
```

---

## 📋 VERIFICACIÓN DE COMPATIBILIDAD

### **ConversationMemory Model** (models.py línea 129)

```python
class ConversationMemory(BaseModel):
    user_message: str
    tool_used: Optional[ToolType] = None
    raw_tool_data: Optional[Dict[str, Any]] = None
    assistant_response: str
    timestamp: datetime
    prompt_mode: PromptMode
    metadata: Optional[Dict[str, Any]] = None
```

**✅ Contiene toda la información necesaria** para reconstruir el historial.

---

## 🚨 RIESGOS Y CONSIDERACIONES

### **1. Formato de ChatMemoryBuffer**

**Riesgo**: La API de `ChatMemoryBuffer` puede variar entre versiones de LlamaIndex.

**Mitigación**: 
- Revisar documentación de LlamaIndex 0.10.55
- Probar localmente antes de desplegar
- Agregar manejo de excepciones robusto

### **2. Límite de Tokens**

**Problema**: Si el historial en Redis excede 3000 tokens, el buffer se truncará.

**Solución**:
- Implementar truncamiento inteligente (mantener mensajes más recientes)
- Considerar aumentar límite si es necesario

### **3. Rendimiento**

**Impacto**: Cargar desde Redis en cada creación de engine puede ser lento.

**Optimización**:
- Mantener caché en memoria (`self.chat_engines`)
- Solo cargar desde Redis si no está en caché
- Implementar TTL en caché (ej: 30 minutos)

### **4. Sincronización**

**Problema**: Si se modifica el historial en Redis mientras el engine está en caché.

**Solución Actual**: No es un problema porque:
- Solo se agrega al final (`LPUSH`)
- El engine en caché mantiene su propia memoria
- La próxima carga desde Redis tendrá el historial completo

---

## ✅ CRITERIOS DE ÉXITO

Una vez implementada la solución:

1. **Test de Reinicio**:
   ```bash
   # Consulta 1
   curl -X POST .../chat -d '{"promptData": "Mi nombre es Juan", "sessionId": "test_001"}'
   
   # Reiniciar contenedor
   docker restart gm-general-chat
   
   # Consulta 2 (debe recordar)
   curl -X POST .../chat -d '{"promptData": "¿Cuál es mi nombre?", "sessionId": "test_001"}'
   # Esperado: "Tu nombre es Juan"
   ```

2. **Test de Múltiples Sesiones**:
   - Sesión A y B no deben interferir
   - Cada sesión mantiene su propio contexto

3. **Test de Persistencia a Largo Plazo**:
   - Consultas separadas por horas deben mantener contexto
   - TTL de 7 días debe respetarse

---

## 📝 PRÓXIMOS PASOS

### **Fase 1: Investigación (30 min)**
- [ ] Revisar documentación de `ChatMemoryBuffer` en LlamaIndex 0.10.55
- [ ] Verificar API para agregar mensajes al buffer
- [ ] Confirmar formato de `ChatMessage`

### **Fase 2: Implementación (1 hora)**
- [ ] Crear `load_conversation_memory_from_redis()`
- [ ] Modificar `get_or_create_chat_engine()`
- [ ] Agregar logs de debugging

### **Fase 3: Testing Local (30 min)**
- [ ] Test básico de carga
- [ ] Test de reinicio
- [ ] Test de múltiples sesiones

### **Fase 4: Despliegue (15 min)**
- [ ] Commit y push
- [ ] Despliegue en producción
- [ ] Validación con `test_production.sh`

---

## 🔗 Referencias

- **LlamaIndex ChatMemoryBuffer**: https://docs.llamaindex.ai/en/stable/module_guides/storing/chat_stores/
- **Redis Lists**: https://redis.io/commands/lrange/
- **Código actual**: `SERVICES/gm_general_chat/main.py`
  - `get_or_create_chat_engine()`: Líneas 200-265
  - `save_conversation_memory()`: Líneas 309-333
  - `unified_chat_endpoint()`: Líneas 644-900

---

## 📊 Resumen Ejecutivo

**Estado Actual**: ❌ La persistencia NO funciona entre reinicios  
**Causa Raíz**: La memoria solo se recupera del caché en memoria, no de Redis  
**Solución**: Implementar carga de historial desde Redis al crear engines  
**Complejidad**: Media (1-2 horas de implementación)  
**Riesgo**: Bajo (cambio localizado, con fallback a memoria nueva)  
**Impacto**: Alto (funcionalidad crítica para UX)
