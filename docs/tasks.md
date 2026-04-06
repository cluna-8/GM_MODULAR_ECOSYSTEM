# TASKS.md — Tareas Pendientes GoMedisys
**Local only — no se commitea al repo.**
Actualizar este archivo al terminar cada tarea o al descubrir nuevas.

---

## Leyenda
- `[ ]` Pendiente
- `[~]` En progreso
- `[x]` Completado
- `[!]` Bloqueante para producción

---

## Gateway — ADM_MODULAR

### Seguridad (bloqueantes para prod)
- `[!]` Proteger `POST /admin/tokens` con autenticación — actualmente abierto a cualquiera
- `[!]` Restringir CORS: cambiar `allow_origins=["*"]` por lista explícita de dominios HIS
- `[!]` Cambiar `SECRET_KEY` del default hardcodeado (`una_clave_muy_secreta_para_produccion` en `auth.py`) por variable de entorno obligatoria
- `[ ]` Agregar rate limiting por token (evitar abuso de API key)

### Logging y errores
- `[ ]` **Agregar logs de error estructurados en el proxy:** cuando el backend devuelve 5xx, registrar en `api_logs` con `error_type` y `error_detail` — actualmente solo se lanza HTTP 502 sin trazabilidad
- `[ ]` Loguear cuando el auditor intercepta (actualmente el log tiene `tokens=0` pero no indica explícitamente que fue intercepción vs error de red)
- `[ ]` Agregar campo `response_time_ms` en `APILog` para detectar latencia por módulo
- `[ ]` Endpoint `GET /admin/errors` — lista los últimos errores 502/4xx del gateway

### Features
- `[ ]` Roles funcionales: actualmente `admin/user/monitor` están en DB pero no se validan en ningún endpoint
- `[ ]` Quota por token: bloquear llamadas cuando `total_tokens_consumed` supera un límite configurable
- `[ ]` `DELETE /admin/tokens/{token}` — revocar API keys
- `[ ]` Migrar DB a Postgres para producción real (actualmente SQLite)

---

## medical_auditor

### Logging y errores
- `[ ]` **Registrar cuando la llamada a GPT-4o-mini falla** — actualmente el fallback es silencioso (`status=OK` sin aviso), en producción se necesita saber si el auditor está operativo o degrado
- `[ ]` Endpoint `GET /audit/health/detailed` — reporta estado de Redis, embeddings y GPT por separado
- `[ ]` Log de cache hits/misses para monitorear eficiencia del caché semántico

### Funcionalidad
- `[ ]` Ajustar umbral del auditor para consultas de seguimiento sin sujeto explícito — los profesionales HIS hacen preguntas en contexto conversacional válido
- `[ ]` `GET /audit/cache/stats` — mostrar tamaño del índice HNSW, entradas activas, TTL promedio
- `[ ]` `DELETE /audit/cache` — limpiar caché semántico sin reiniciar el servicio

---

## gm_general_chat (Chat 1 — Médico General)

### Bugs confirmados
- `[!]` **ICD-10 tool no dispara la API** — al enviar `"tools": "icd10"` el LLM responde de memoria. Investigar `execute_tool_search()` en `main.py` — posiblemente el mapeo del enum `ToolType.ICD10` no coincide con el handler registrado
- `[!]` **clinical_trials tool no dispara la API** — mismo síntoma que ICD-10. Revisar el handler de `ToolType.CLINICAL_TRIALS` dentro de `execute_tool_search()`
- `[ ]` Probar `scraping` tool — nunca se verificó en producción

### Logging y errores
- `[ ]` **Loguear errores de llamadas a herramientas externas (FDA, PubMed, etc.)** — si la API externa falla, el LLM responde de memoria sin avisar. Agregar `tool_error` en la respuesta cuando la herramienta lanza excepción
- `[ ]` Registrar en logs cuando Redis no está disponible para sesiones (actualmente silencioso)
- `[ ]` Agregar `X-Session-Id` en headers de respuesta para que el gateway pueda capturarlo sin parsear el body

### Features
- `[ ]` Endpoint `GET /sessions/{session_id}/history` — retornar historial completo de la sesión en texto plano (útil para auditoría HIS)
- `[ ]` Limpiar sesión: `DELETE /sessions/{session_id}`
- `[ ]` Soporte multimodal: recibir imagen + texto (radiografías, ECGs) — requiere upgrade a gpt-4o con vision

---

## gm_ch_summary (Chat 2 — Resumen Clínico) — NUEVO, no en prod

### Bugs / Pendientes
- `[ ]` `data.response` llega como string JSON — evaluar si el servicio debería devolver el objeto ya parseado para simplificar la integración del cliente HIS
- `[ ]` Agregar validación de longitud mínima del input — textos muy cortos (<50 chars) generan resúmenes vacíos o inventados
- `[ ]` Probar con textos reales de HIS (HTML con tags, tablas, caracteres especiales) — actualmente solo probado con texto limpio

### Logging y errores
- `[ ]` Si GPT devuelve JSON malformado, el servicio no lo maneja — agregar try/parse con fallback a respuesta de error estructurado
- `[ ]` Agregar logs de error cuando el texto de entrada tiene caracteres no imprimibles que sobreviven la limpieza

### Features
- `[ ]` Soporte para múltiples historias en un solo request (batch summarization)
- `[ ]` Modo diff: comparar dos versiones de una historia y resaltar cambios clínicos relevantes
- `[ ]` Integrar auditor post-proceso (actualmente `auditor_alert` siempre es `false`, no llama al medical_auditor)

---

## gm_voice (Chat 3 — Extractor Voz a JSON) — Sin implementar

> Módulo reservado en gateway como `chat3 → http://gm-voice:7007` pero el servicio no existe aún.

- `[ ]` Definir stack: Whisper (OpenAI) para transcripción o Azure Speech
- `[ ]` Schema de salida: JSON con campos clínicos extraídos del audio (diagnóstico, medicamentos, signos vitales)
- `[ ]` Endpoint: `POST /transcribe` recibe audio base64 o multipart
- `[ ]` Integrar con medical_auditor post-transcripción
- `[ ]` Crear Dockerfile y agregar al docker-compose
- `[ ]` Probar latencia — el audio médico puede ser largo (>5 min de consulta)

---

## gm_diagnosis (Chat 4 — Agente de Diagnóstico) — Sin implementar

> Módulo reservado en gateway como `chat4 → http://gm-diagnosis:7008` pero el servicio no existe aún.

- `[ ]` Definir flujo: recibe síntomas → devuelve diagnósticos diferenciales ordenados por probabilidad
- `[ ]` Integrar ICD-10 para codificar diagnósticos sugeridos
- `[ ]` Integrar PubMed para justificar cada diagnóstico con evidencia
- `[ ]` Integrar FDA para sugerir tratamientos basados en diagnóstico
- `[ ]` Requiere auditor estricto — diagnósticos erróneos tienen impacto directo en pacientes
- `[ ]` Crear Dockerfile y agregar al docker-compose
- `[ ]` Definir disclaimer clínico obligatorio en todas las respuestas

---

## Infraestructura General

- `[ ]` Crear `docker network create gomedisys-net` en script de setup inicial — actualmente falla silenciosamente si no existe
- `[ ]` Script de startup completo: network → compose up → seed gateway → health check de todos los servicios
- `[ ]` Configurar Redis con persistencia (AOF o RDB) — actualmente los datos de sesión se pierden si el contenedor se detiene
- `[ ]` Definir estrategia de backup para SQLite del gateway
- `[ ]` Health check en docker-compose para cada servicio (actualmente `restart: always` pero sin `healthcheck`)

---

## Completado recientemente
- `[x]` Fix session memory: `validation_alias="sessionId"` roto en ChatRequest
- `[x]` Exponer `/audit/feedback` en gateway (antes solo en `:7005` directo)
- `[x]` Validación de payload vacío en gateway → HTTP 422
- `[x]` Crear `AI_CONTEXT.md` con arquitectura completa para agentes AI
- `[x]` Remover archivos de test del repositorio git
- `[x]` Tag v1.1.0
