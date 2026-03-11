# Plan de Implementación: Persistencia de Sesión

**Fecha**: 2026-02-11  
**Estado**: Pendiente  
**Prioridad**: Media  
**Objetivo**: Implementar memoria conversacional persistente entre múltiples consultas del mismo usuario

---

## 📋 Contexto

Actualmente, el sistema **funciona correctamente** para:
- ✅ Chat estándar (respuestas médicas)
- ✅ MCP (ICD-10 y otras herramientas)
- ✅ Auditoría de seguridad (detección de alergias)
- ✅ Logging forense (trazas en `audit_log.jsonl`)

**Problema identificado**: El sistema **no retiene el contexto conversacional** entre consultas del mismo `session_id`. Cada consulta se procesa como si fuera la primera vez.

---

## 🔍 Análisis Técnico

### 1. Arquitectura Actual

```
Usuario → Gateway → gm-general-chat → SimpleChatEngine
                                            ↓
                                    ChatMemoryBuffer
                                            ↓
                                        Redis
```

### 2. Componentes Involucrados

#### **A. SimpleChatEngine** (`main.py` líneas 200-260)
- Crea instancias de `SimpleChatEngine` con `ChatMemoryBuffer`
- **Problema potencial**: La memoria se crea pero podría no persistirse correctamente

#### **B. ChatMemoryBuffer** (LlamaIndex)
- Buffer en memoria para mantener historial de conversación
- **Límite**: 3000 tokens
- **Problema potencial**: Podría no estar sincronizándose con Redis

#### **C. Redis** (conexión en línea 168-177)
- Almacena sesiones y metadatos
- **Problema potencial**: La memoria del chat podría no estar guardándose en Redis

#### **D. save_conversation_memory()** (líneas 296-321)
- Guarda el historial en Redis como JSON
- **Problema potencial**: Podría no estar recuperándose al crear nuevas instancias del engine

---

## 🎯 Plan de Acción

### **Fase 1: Diagnóstico (30 min)**

#### 1.1 Verificar Persistencia en Redis
```bash
# Conectarse a Redis y verificar qué se está guardando
docker exec redis-general redis-cli
> KEYS session:*
> HGETALL session:test_session_123
> KEYS conversation:*
> LRANGE conversation:test_session_123 0 -1
```

**Objetivo**: Confirmar si los datos de conversación se están guardando en Redis.

#### 1.2 Revisar Logs de Creación de Engine
```bash
# Buscar logs de creación/reutilización de chat engines
docker logs gm-general-chat | grep -E "(Created|Reusing|memory)"
```

**Objetivo**: Ver si el sistema está reutilizando engines existentes o creando nuevos cada vez.

#### 1.3 Test de Persistencia Local
```bash
# Test 1: Primera consulta
curl -X POST http://localhost:8000/medical/chat \
  -H "Authorization: Bearer hcg_maestro_123" \
  -d '{"promptData": "Mi nombre es Juan", "sessionId": "test_mem_001", "IAType": "medical"}'

# Test 2: Segunda consulta (misma sesión)
curl -X POST http://localhost:8000/medical/chat \
  -H "Authorization: Bearer hcg_maestro_123" \
  -d '{"promptData": "¿Cuál es mi nombre?", "sessionId": "test_mem_001", "IAType": "medical"}'
```

**Objetivo**: Reproducir el problema en local y analizar el comportamiento.

---

### **Fase 2: Identificación del Problema (45 min)**

#### 2.1 Revisar `get_or_create_chat_engine()`
**Archivo**: `main.py` líneas 200-260

**Puntos a verificar**:
- ✅ ¿Se está reutilizando `existing_memory` correctamente?
- ✅ ¿El `engine_key` es consistente entre llamadas?
- ✅ ¿La memoria se está pasando al nuevo engine?

**Código actual**:
```python
if engine_key in self.chat_engines:
    engine = self.chat_engines[engine_key]
    existing_memory = getattr(engine, "memory", getattr(engine, "_memory", None))
```

**Posible problema**: 
- La memoria podría estar vacía porque no se está **cargando desde Redis** al crear el engine.

#### 2.2 Revisar `save_conversation_memory()`
**Archivo**: `main.py` líneas 296-321

**Puntos a verificar**:
- ✅ ¿Se está guardando correctamente en Redis?
- ✅ ¿El formato JSON es correcto?
- ✅ ¿Se está usando la clave correcta (`conversation:{session_id}`)?

#### 2.3 Verificar Recuperación de Memoria
**Pregunta clave**: ¿Existe una función que **cargue** la memoria desde Redis al crear un nuevo engine?

**Búsqueda**:
```bash
grep -n "LRANGE\|conversation:" main.py
grep -n "from_defaults.*memory" main.py
```

**Hipótesis**: Probablemente **falta** la lógica para cargar el historial desde Redis.

---

### **Fase 3: Implementación de la Solución (1-2 horas)**

#### 3.1 Crear Función de Recuperación de Memoria

**Nueva función** en `HybridChatConfig`:
```python
async def load_conversation_memory(self, session_id: str) -> Optional[ChatMemoryBuffer]:
    """Cargar historial de conversación desde Redis"""
    if not self.redis_client:
        return None
    
    try:
        conversation_key = f"conversation:{session_id}"
        messages = await self.redis_client.lrange(conversation_key, 0, -1)
        
        if not messages:
            return None
        
        # Crear buffer de memoria
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
        
        # Cargar mensajes en el buffer
        for msg_json in messages:
            msg = json.loads(msg_json)
            # Agregar al buffer (formato específico de LlamaIndex)
            # TODO: Implementar según API de ChatMemoryBuffer
        
        logger.info(f"Loaded {len(messages)} messages for session {session_id}")
        return memory
        
    except Exception as e:
        logger.error(f"Error loading conversation memory: {e}")
        return None
```

#### 3.2 Modificar `get_or_create_chat_engine()`

**Cambio en líneas 229-236**:
```python
# Create or reuse memory buffer
if existing_memory:
    memory = existing_memory
else:
    # NUEVO: Intentar cargar desde Redis primero
    memory = await self.load_conversation_memory(session_id)
    
    if not memory:
        # Si no hay memoria en Redis, crear nueva
        try:
            memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
        except Exception:
            memory = ChatMemoryBuffer.from_defaults()
```

#### 3.3 Asegurar Formato Correcto en Redis

**Verificar** que `save_conversation_memory()` guarde en un formato compatible con la carga.

---

### **Fase 4: Testing (30 min)**

#### 4.1 Test Local Completo
```bash
# Ejecutar test de persistencia
./test_local.sh

# Test manual específico
curl -X POST http://localhost:8000/medical/chat \
  -H "Authorization: Bearer hcg_maestro_123" \
  -d '{"promptData": "Soy diabético tipo 2", "sessionId": "test_persist", "IAType": "medical"}'

curl -X POST http://localhost:8000/medical/chat \
  -H "Authorization: Bearer hcg_maestro_123" \
  -d '{"promptData": "¿Qué tipo de diabetes tengo?", "sessionId": "test_persist", "IAType": "medical"}'
```

**Resultado esperado**: La segunda consulta debe responder "diabetes tipo 2".

#### 4.2 Verificar en Redis
```bash
docker exec redis-general redis-cli LRANGE conversation:test_persist 0 -1
```

#### 4.3 Test de Múltiples Sesiones
Verificar que sesiones diferentes no interfieran entre sí.

---

### **Fase 5: Despliegue (15 min)**

#### 5.1 Commit y Push
```bash
cd SERVICES/gm_general_chat
git add main.py
git commit -m "feat: Implement session memory persistence with Redis"
git push origin main
```

#### 5.2 Despliegue en Producción
```bash
ssh sysadmins@20.186.59.6 "cd /home/sysadmins/CHAT-Agent/DEPLOYMENT/SERVICES/GM_GENERAL_CHAT && git pull origin main && cd /home/sysadmins/CHAT-Agent/DEPLOYMENT && docker compose up -d --build --force-recreate gm-general-chat"
```

#### 5.3 Test en Producción
```bash
./test_production.sh
```

---

## 📊 Criterios de Éxito

- ✅ El test de persistencia de sesión pasa (5/7 en `test_production.sh`)
- ✅ Redis contiene el historial de conversación
- ✅ Múltiples consultas en la misma sesión mantienen contexto
- ✅ Sesiones diferentes no interfieren entre sí
- ✅ El sistema sigue funcionando para chat estándar y MCP

---

## 🚨 Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Incompatibilidad con API de LlamaIndex | Media | Alto | Revisar documentación de `ChatMemoryBuffer` antes de implementar |
| Sobrecarga de Redis | Baja | Medio | Implementar TTL (24h) para conversaciones antiguas |
| Pérdida de contexto en prompts largos | Media | Medio | Mantener límite de 3000 tokens y truncar si es necesario |
| Conflicto con custom_system_prompt | Media | Alto | Asegurar que la memoria se mantenga al actualizar el prompt |

---

## 📝 Notas Adicionales

### Alternativas Consideradas

1. **Usar Redis como único almacén de memoria**
   - Pros: Más simple, persistencia garantizada
   - Contras: Requiere serialización/deserialización en cada consulta

2. **Mantener engines en memoria con TTL**
   - Pros: Más rápido, menos llamadas a Redis
   - Contras: Pérdida de memoria si el contenedor se reinicia

3. **Implementación actual (híbrida)**
   - Pros: Balance entre velocidad y persistencia
   - Contras: Requiere sincronización correcta

### Referencias

- **LlamaIndex ChatMemoryBuffer**: https://docs.llamaindex.ai/en/stable/module_guides/storing/chat_stores/
- **Redis Lists**: https://redis.io/commands/lrange/
- **Código actual**: `SERVICES/gm_general_chat/main.py` líneas 200-321

---

## ✅ Checklist de Implementación

- [ ] Fase 1: Diagnóstico completado
- [ ] Fase 2: Problema identificado
- [ ] Fase 3: Solución implementada
- [ ] Fase 4: Tests locales pasando
- [ ] Fase 5: Desplegado en producción
- [ ] Documentación actualizada
- [ ] Test de persistencia en `test_production.sh` pasando

---

**Próximos pasos**: Ejecutar Fase 1 (Diagnóstico) para confirmar la hipótesis del problema.
