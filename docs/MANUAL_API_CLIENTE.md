# 📘 Manual de Integración API - GoMedisys

Bienvenido a la API de GoMedisys. Este manual detalla cómo integrar el sistema de Inteligencia Artificial Médica en sus aplicaciones, gestionar la seguridad y optimizar el uso de tokens.

---

## 1. Autenticación y Seguridad
Todas las peticiones a la API deben incluir un token de acceso Bearer en los encabezados HTTP.

### **Obtención de Token**
El administrador le proporcionará un token con el formato `hcg_...`. Este token identifica a su departamento y controla su consumo.

**Ejemplo de Header:**
```http
Authorization: Bearer hcg_tu_token_aqui
```

---

## 2. Endpoint Principal: Chat Médico
El punto de entrada unificado para todas las consultas.

**POST** `/v1/chat1/chat`

### **Estructura de la Petición (JSON)**
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `message` | String | La consulta clínica o pregunta del médico. |
| `session_id` | String | ID para mantener la memoria de la conversación (opcional). |
| `context` | Object | Datos del paciente (alergias, edad, diagnósticos) **CRÍTICO PARA SEGURIDAD**. |
| `prompt_mode` | String | Modo de comportamiento: `medical`, `pediatric`, `emergency`, `pharmacy`. |
| `tools` | String | (Opcional) Herramienta externa a invocar: `fda`, `pubmed`, `icd10`, `clinical_trials`, `scraping`. |

### **Ejemplo de Consulta con Contexto (Recomendado)**
```json
{
  "message": "¿Puedo administrar Amoxicilina por dolor de garganta?",
  "sessionId": "consulta_urg_001",
  "prompt_mode": "medical",
  "context": {
    "alergias": "Penicilina, Polen",
    "edad": "25 años",
    "diagnostico_previo": "Faringitis"
  }
}
```

### **3. Ejemplos de Uso**

#### **A) Consulta Estándar (Sin prompt adicional)**
Ideal para consultas rápidas basadas en el comportamiento predefinido.
```bash
curl -X POST http://server:8000/v1/chat1/chat \
-H "Authorization: Bearer hcg_tu_token" \
-d '{
  "message": "¿Cuál es el protocolo para asma?",
  "prompt_mode": "medical"
}'
```

#### **B) Consulta Avanzada (Con Prompt de Especialista)**
Permite al cliente forzar un estilo de respuesta o directriz específica.
```bash
curl -X POST http://server:8000/v1/chat1/chat \
-H "Authorization: Bearer hcg_tu_token" \
-d '{
  "message": "Paciente con sibilancias.",
  "prompt_mode": "emergency",
  "prompt_data": "Responde solo con los 3 pasos de acción inmediata, sin explicaciones largas."
}'
```

#### **C) Consulta con Conectividad Externa (MCP)**
Permite al asistente consultar bases de datos externas en tiempo real para obtener información oficial y precisa.
```bash
curl -X POST http://server:8000/v1/chat1/chat \
-H "Authorization: Bearer hcg_tu_token" \
-d '{
  "message": "código diagnósticos de asma",
  "prompt_mode": "medical",
  "tools": "icd10"
}'
```

---

## 4. Control de Costos y Tokens
La API devuelve el consumo exacto en cada respuesta para que pueda monitorear su presupuesto.

```json
"usage": {
  "prompt_tokens": 150,
  "completion_tokens": 200,
  "total_tokens": 350
}
```

### **Optimización por Caché**
GoMedisys incluye:
- **Caché inteligente**: Reutiliza respuestas similares, respondiendo instantáneamente sin consumir tokens de IA principal, ahorrando hasta un 25% en costos operativos.
- **Anonimización**: El sistema opera únicamente con datos clínicos, sin requerir identificadores personales (PII).

---

## �️ Conectividad Multi-Agente (MCP)
GoMedisys utiliza el **Model Context Protocol (MCP)** para extender las capacidades del asistente mediante herramientas especializadas:

- **FDA Search**: Consulta la base de datos oficial de fármacos para posologías e interacciones.
- **PubMed**: Búsqueda en literatura científica revisada por pares para medicina basada en evidencia.
- **Clinical Trials**: Localización de ensayos clínicos activos y protocolos de investigación.
- **ICD-10**: Búsqueda inteligente de códigos internacionales de enfermedades.
- **Medical Scraping**: Extracción selectiva de datos de sitios de confianza (Mayo Clinic, WebMD).

---
GoMedisys sigue un principio de **"Zero-PII Access"**:

1. **Exclusión de Identidad**: El sistema NO requiere ni debe recibir Nombres, IDs nacionales, Direcciones o Teléfonos de pacientes.
2. **Contexto Clínico Puro**: Solo se procesan variables clínicas (Edad, Género, Alergias, Diagnósticos) necesarias para la seguridad médica.
3. **Capa del Cliente**: Es responsabilidad de la integración del cliente (HIS/App) anonimizar la petición antes de enviarla a la API de GoMedisys.
4. **Almacenamiento Seguro**: Los logs de auditoría y entrenamiento solo contienen el contexto clínico inyectado.

---

## 5. Auditoría y Trazabilidad (Forensics)
Cada respuesta incluye una validación del **Medical Auditor**.

### **Estados de Seguridad:**
1. **SUCCESS**: La respuesta es segura.
2. **ALERT**: Se muestra la respuesta pero con una advertencia crítica (ej. alergia detectada).
3. **REJECTED**: La consulta fue bloqueada (ej. tema no médico o incoherencia clínica).

### **Inspección de Traza:**
Para auditorías legales o revisión médica, puede consultar el trazo completo de cualquier sesión:
**GET** `/admin/trace/{session_id}`

---

## 6. Ciclo de Mejora (RLHF)
Como cliente, puede participar en el entrenamiento del modelo enviando correcciones de sus médicos expertos.

**POST** `/audit/feedback`
```json
{
  "session_id": "consulta_urg_001",
  "rating": 1,
  "is_dangerous": true,
  "comment": "Sugirió un fármaco que no está en nuestro arsenal local.",
  "suggested_response": "Debe usar [Fármaco B] según protocolo interno."
}
```

---

## 7. Códigos de Error Comunes
- `401 Unauthorized`: Token inválido o expirado.
- `502 Bad Gateway`: Error de conexión con el módulo de IA.
- `404 Not Found`: Módulo o sesión no encontrada.

---

**Soporte Técnico:**   
**Versión API:** 2.0.0
