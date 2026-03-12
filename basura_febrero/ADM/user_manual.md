# 👤 Manual de Usuario - Healthcare API Gateway

## 🎯 Introducción

El Healthcare API Gateway es un sistema de autenticación y control de acceso para la API médica que permite:
- Gestión de usuarios y roles
- Control de tokens de acceso
- Monitoreo de uso y costos
- Proxy seguro para consultas médicas

## 👥 Roles y Permisos

### 🔴 ADMIN - Administrador
- **Permisos:** Control total del sistema
- **Puede:**
  - Crear/eliminar usuarios
  - Crear/revocar tokens
  - Ver todas las estadísticas
  - Monitorear sesiones
  - Usar API médica

### 🔵 USER - Usuario Médico
- **Permisos:** Uso de la API médica
- **Puede:**
  - Usar chat médico
  - Acceder a herramientas médicas
  - Ver sus propias sesiones
  - Ver sus estadísticas

### 🟡 MONITOR - Supervisor
- **Permisos:** Solo visualización
- **Puede:**
  - Ver estadísticas del sistema
  - Monitorear sesiones
  - Ver reportes de uso

## 🔐 Gestión de Usuarios

### Crear Usuario (Solo ADMIN)

```bash
curl -X POST "http://localhost:8000/admin/users" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172" \
-d '{
  "username": "dr_rodriguez",
  "email": "rodriguez@hospital.com",
  "role": "user",
  "password": "MiPassword123!"
}'
```

**Roles disponibles:** `admin`, `user`, `monitor`

### Listar Usuarios

```bash
curl -X GET "http://localhost:8000/admin/users" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

### Desactivar Usuario

```bash
curl -X DELETE "http://localhost:8000/admin/users/{user_id}" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

## 🗝️ Gestión de Tokens

### Crear Token para Usuario

```bash
curl -X POST "http://localhost:8000/admin/tokens" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172" \
-d '{
  "user_id": 4,
  "name": "Dr. Rodriguez - Token Principal"
}'
```

### Listar Todos los Tokens

```bash
curl -X GET "http://localhost:8000/admin/tokens" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

### Revocar Token

```bash
curl -X DELETE "http://localhost:8000/admin/tokens/{token_id}" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

## 📊 Monitoreo de Costos

### Estadísticas del Sistema (ADMIN/MONITOR)

```bash
curl -X GET "http://localhost:8000/monitor/stats/system" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

**Respuesta:**
```json
{
  "total_users": 4,
  "active_tokens": 3,
  "total_sessions": 25,
  "total_requests": 150,
  "total_tokens_consumed": 45000,
  "requests_last_24h": 12,
  "top_tools_used": [
    {"tool": "fda", "count": 45},
    {"tool": "pubmed", "count": 23}
  ]
}
```

### Estadísticas por Token

```bash
curl -X GET "http://localhost:8000/monitor/stats/token/{token_id}" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

### Mis Estadísticas (Usuario)

```bash
curl -X GET "http://localhost:8000/user/my-stats" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1"
```

### Historial de Requests

```bash
curl -X GET "http://localhost:8000/monitor/requests?limit=50" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

### Mis Requests (Usuario)

```bash
curl -X GET "http://localhost:8000/user/my-requests?limit=10" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1"
```

## 💬 Uso de la API Médica

### Chat Básico

```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "¿Cuáles son los síntomas de la hipertensión?",
  "session": "consulta_001"
}'
```

### Chat con Herramientas

```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "Busca información sobre aspirina en FDA",
  "session": "consulta_fda_001",
  "tools": "fda",
  "prompt_mode": "medical",
  "language": "es"
}'
```

### Personalidades/Modos de Prompt

**Modos disponibles:**
- `medical` - Modo médico profesional (por defecto)
- `patient` - Explicaciones para pacientes
- `research` - Modo de investigación
- `clinical` - Enfoque clínico
- `educational` - Modo educativo

```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "Explica qué es la diabetes",
  "prompt_mode": "patient",
  "language": "es"
}'
```

## 🛠️ Herramientas Médicas Directas

### FDA (Medicamentos)

```bash
curl -X POST "http://localhost:8000/medical/tools/fda" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "query": "ibuprofeno",
  "max_results": 5,
  "format_response": true,
  "language": "es"
}'
```

### PubMed (Investigación)

```bash
curl -X POST "http://localhost:8000/medical/tools/pubmed" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "query": "diabetes treatment 2024",
  "max_results": 3
}'
```

### Clinical Trials

```bash
curl -X POST "http://localhost:8000/medical/tools/clinical-trials" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "query": "cancer immunotherapy",
  "max_results": 5
}'
```

### ICD-10 (Códigos)

```bash
curl -X POST "http://localhost:8000/medical/tools/icd10" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "query": "diabetes",
  "max_results": 10
}'
```

### Web Scraping

```bash
curl -X POST "http://localhost:8000/medical/tools/scraping" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "query": "latest covid guidelines WHO",
  "max_results": 3
}'
```

## 📱 Gestión de Sesiones

### Ver Mis Sesiones

```bash
curl -X GET "http://localhost:8000/user/my-sessions" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1"
```

### Ver Todas las Sesiones (ADMIN/MONITOR)

```bash
curl -X GET "http://localhost:8000/monitor/sessions" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

### Detalles de Sesión Específica

```bash
curl -X GET "http://localhost:8000/monitor/sessions/{session_id}" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

### Eliminar Sesión

```bash
curl -X DELETE "http://localhost:8000/medical/sessions/{session_id}" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1"
```

## 🌐 WebSocket (Chat en Tiempo Real)

```javascript
// Conectar a WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/chat/hcg_gomedisys_user_demo_8025A4507BCBD1D1');

// Enviar mensaje
ws.send(JSON.stringify({
    message: "¿Qué es la hipertensión?",
    session: "ws_session_001",
    tools: "fda",
    prompt_mode: "medical"
}));

// Recibir respuesta
ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log(response);
};
```

## 🔍 Ejemplos de Uso Avanzado

### Chat Multiherramienta

```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "Necesito información completa sobre metformina: efectos, estudios recientes y ensayos clínicos",
  "session": "investigacion_metformina",
  "tools": "fda,pubmed,clinical-trials",
  "prompt_mode": "research",
  "language": "es"
}'
```

### Consulta de Seguimiento

```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "¿Hay alguna contraindicación con warfarina?",
  "session": "investigacion_metformina",
  "prompt_mode": "clinical"
}'
```

## 📋 Códigos de Respuesta

| Código | Significado |
|--------|-------------|
| 200 | Éxito |
| 401 | Token inválido o expirado |
| 403 | Sin permisos para este endpoint |
| 404 | Recurso no encontrado |
| 429 | Límite de requests excedido |
| 503 | API médica no disponible |

## ⚡ Tips de Uso

1. **Sesiones:** Usa el mismo `session_id` para mantener contexto
2. **Herramientas:** Combina múltiples herramientas con comas: `"fda,pubmed"`
3. **Idioma:** El sistema detecta automáticamente, pero puedes forzar con `"language": "es"`
4. **Modo:** Ajusta `prompt_mode` según tu audiencia
5. **Monitoreo:** Revisa regularmente el uso de tokens para controlar costos

## 🚨 Límites y Consideraciones

- **Rate Limiting:** 1000 requests/hora por token
- **Timeout:** 60 segundos por request
- **Tamaño:** Máximo 10MB por request
- **Sesiones:** Se mantienen activas 24 horas sin uso
- **Tokens:** No expiran pero pueden ser revocados