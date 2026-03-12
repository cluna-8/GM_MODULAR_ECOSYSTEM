# 🏥 Guía de Administración - Healthcare API Gateway

## 📋 Información General

El Healthcare API Gateway es un sistema de autenticación y control de acceso que gestiona el uso de la API médica. Proporciona herramientas completas para administrar usuarios, tokens y monitorear el uso de recursos.

### Arquitectura del Sistema
- **API Gateway**: Puerto 8000 - Autenticación y proxy
- **API Médica**: Puerto 7005 - Procesamiento médico interno
- **Base de Datos**: SQLite - Almacenamiento de usuarios y estadísticas

---

## 🔐 Gestión de Usuarios y Roles

### Roles Disponibles

| Rol | Descripción | Permisos |
|-----|-------------|----------|
| **ADMIN** | Administrador completo | Gestión total del sistema |
| **USER** | Usuario médico | Acceso a chat y herramientas médicas |
| **MONITOR** | Supervisor | Solo visualización de estadísticas |

### Usuarios Predefinidos

El sistema viene con estos usuarios por defecto:

```
🔹 admin / admin@healthcare.local (ADMIN)
🔹 doctor1 / doctor1@example.com (USER)  
🔹 monitor1 / monitor1@example.com (MONITOR)
```

**Contraseña por defecto**: `admin123` (cambiar en producción)

---

## 🗝️ Gestión de Tokens API

### Tokens Predefinidos

| Token | Rol | Descripción |
|-------|-----|-------------|
| `hcg_gomedisys_admin_9120B76F636BE172` | ADMIN | Gestión administrativa |
| `hcg_gomedisys_user_demo_8025A4507BCBD1D1` | USER | Acceso médico demo |
| `hcg_gomedisys_monitor_32B581AA6DA7442D` | MONITOR | Supervisión |

### Crear Nuevo Usuario

**Endpoint**: `POST /admin/users`  
**Autenticación**: Token ADMIN requerido

```bash
curl -X POST "http://localhost:8000/admin/users" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172" \
-d '{
  "username": "doctor_smith",
  "email": "smith@hospital.com",
  "role": "user",
  "password": "secure_password123"
}'
```

**Respuesta Exitosa**:
```json
{
  "id": 4,
  "username": "doctor_smith",
  "email": "smith@hospital.com", 
  "role": "user",
  "is_active": true,
  "created_at": "2025-07-24T20:30:00Z"
}
```

### Crear Token para Usuario

**Endpoint**: `POST /admin/tokens`  
**Autenticación**: Token ADMIN requerido

```bash
curl -X POST "http://localhost:8000/admin/tokens" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172" \
-d '{
  "user_id": 4,
  "name": "Dr. Smith - Production Token"
}'
```

**Respuesta Exitosa**:
```json
{
  "id": 10,
  "token": "hcg_Xy9kP2mNvB8qR5tW3zL7nF1dH6sA9jC4",
  "name": "Dr. Smith - Production Token",
  "status": "active",
  "created_at": "2025-07-24T20:35:00Z",
  "total_requests": 0,
  "total_tokens_consumed": 0,
  "user": {
    "id": 4,
    "username": "doctor_smith",
    "email": "smith@hospital.com",
    "role": "user"
  }
}
```

### Listar Todos los Usuarios

```bash
curl -X GET "http://localhost:8000/admin/users" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
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

### Desactivar Usuario

```bash
curl -X DELETE "http://localhost:8000/admin/users/{user_id}" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

---

## 📊 Control de Gastos y Monitoreo

### Estadísticas del Sistema

**Endpoint**: `GET /monitor/stats/system`  
**Autenticación**: Token ADMIN o MONITOR

```bash
curl -X GET "http://localhost:8000/monitor/stats/system" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

**Respuesta**:
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
    {"tool": "pubmed", "count": 23},
    {"tool": "icd10", "count": 18}
  ]
}
```

### Estadísticas por Token

**Endpoint**: `GET /monitor/stats/token/{token_id}`

```bash
curl -X GET "http://localhost:8000/monitor/stats/token/10" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

**Respuesta**:
```json
{
  "total_tokens": 1250,
  "total_requests": 45,
  "active_sessions": 2,
  "last_activity": "2025-07-24T20:45:00Z"
}
```

### Listar Sesiones Activas

```bash
curl -X GET "http://localhost:8000/monitor/sessions" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

### Historial de Requests

```bash
curl -X GET "http://localhost:8000/monitor/requests?limit=50" \
-H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172"
```

---

## 💰 Control de Costos

### Métricas Importantes

1. **total_tokens_consumed**: Tokens totales usados por el sistema
2. **total_requests**: Número total de peticiones
3. **processing_time**: Tiempo de procesamiento por request
4. **tool_used**: Herramienta utilizada (FDA, PubMed, etc.)

### Alertas de Uso Recomendadas

**Configurar alertas cuando**:
- Un token supere 10,000 tokens/día
- Más de 1,000 requests/hora en el sistema
- Tiempo de procesamiento > 30 segundos
- Más de 100 errores/hora

### Límites Sugeridos por Rol

| Rol | Requests/Día | Tokens/Día | Herramientas |
|-----|--------------|------------|--------------|
| USER | 500 | 50,000 | Todas |
| MONITOR | 100 | 5,000 | Solo consultas |
| ADMIN | Ilimitado | Ilimitado | Todas |

---

## 🔧 Health Check y Status

### Verificar Estado del Sistema

```bash
curl -X GET "http://localhost:8000/health"
```

**Respuesta Saludable**:
```json
{
  "status": "healthy",
  "timestamp": "2025-07-24T20:50:00Z",
  "services": {
    "database": {
      "status": "healthy",
      "connection": true,
      "tables_exist": true,
      "users": 4,
      "tokens": 3
    },
    "medical_api": {
      "status": "healthy",
      "url": "http://healthcare-chat-api:7005"
    }
  },
  "version": "1.0.0"
}
```

### Información de la API

```bash
curl -X GET "http://localhost:8000/info"
```

---

## 📱 Dashboard de Usuario

### Ver Mis Sesiones

**Endpoint**: `GET /user/my-sessions`  
**Autenticación**: Cualquier token USER

```bash
curl -X GET "http://localhost:8000/user/my-sessions" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1"
```

### Ver Mis Estadísticas

```bash
curl -X GET "http://localhost:8000/user/my-stats" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1"
```

---

## 🚨 Resolución de Problemas

### Errores Comunes

**Error 401 - "Invalid or expired API token"**
- Verificar formato del token (debe empezar con `hcg_`)
- Verificar que el token esté activo
- Verificar que el usuario asociado esté activo

**Error 403 - "User token required for this endpoint"**
- Endpoint médico requiere token USER, no ADMIN
- Usar token con rol correcto

**Error 503 - "Medical API unavailable"**
- API médica (puerto 7005) no está funcionando
- Verificar Docker containers

### Comandos de Diagnóstico

```bash
# Verificar containers
docker-compose ps

# Ver logs del API Gateway
docker logs healthcare-api-gateway

# Ver logs de la API médica
docker logs healthcare-chat-api

# Reiniciar servicios
docker-compose restart
```

---

## 🔒 Consideraciones de Seguridad

### Recomendaciones

1. **Cambiar contraseñas por defecto**
2. **Regenerar tokens en producción**
3. **Configurar HTTPS en producción**
4. **Implementar rate limiting por IP**
5. **Rotar tokens periódicamente**
6. **Monitorear logs de acceso**

### Variables de Entorno Críticas

```env
JWT_SECRET_KEY=your-super-secret-key-change-in-production
DATABASE_URL=sqlite:///./data/healthcare_gateway.db
MEDICAL_API_URL=http://healthcare-chat-api:7005
ENVIRONMENT=production
```

---

## 📞 Soporte

Para soporte técnico o dudas sobre la administración:
- Revisar logs del sistema
- Consultar health checks
- Verificar estadísticas de uso
- Contactar al equipo técnico

---

*Guía actualizada: Julio 2025 | Versión API Gateway: 1.0.0*