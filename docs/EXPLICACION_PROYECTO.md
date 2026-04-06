# 🏥 GoMedisys - Explicación Completa del Proyecto

## 📋 ¿Qué es GoMedisys?

GoMedisys es un **sistema de inteligencia artificial médica** diseñado para ayudar a profesionales de la salud con consultas clínicas de forma segura y precisa. Piensa en él como un "asistente médico virtual" que puede responder preguntas, buscar información médica y validar que las respuestas sean seguras para los pacientes.

---

## 🎯 Objetivo Principal

Crear un chatbot médico que:
- ✅ Responda preguntas clínicas con información precisa
- ✅ Valide que las respuestas sean seguras (no dañen al paciente)
- ✅ Use datos del paciente (edad, alergias, diagnósticos) para personalizar respuestas
- ✅ Registre todo lo que hace para auditorías y mejoras
- ✅ Controle quién puede usar el sistema y cuánto cuesta cada consulta

---

## 🏗️ Arquitectura del Sistema (Los Módulos Principales)

El sistema está dividido en **módulos independientes** que trabajan juntos:

### 1️⃣ **CLINICAL_SANDBOX** (Herramienta de Testing y Desarrollo)
> [!NOTE]
> Este módulo está diseñado exclusivamente para pruebas locales y demostraciones. No se incluye en el despliegue de servidor de producción.
**Tecnología:** React + Vite (JavaScript)
**Puerto:** 5173

**¿Qué hace?**
- Es la **página web** donde los médicos interactúan con el sistema
- Tiene un chat donde escriben sus preguntas
- Permite simular datos de pacientes (edad, género, alergias, diagnósticos)
- Muestra un "inspector técnico" que permite ver todo lo que pasa "bajo el capó"
- Tiene un modo de prueba para intentar "romper" la IA y verificar que es segura

**Ejemplo de uso:**
```
Médico escribe: "¿Qué antibiótico puedo dar a un paciente con alergia a penicilina?"
Sistema muestra: Respuesta + Trazabilidad de seguridad
```

---

### 2️⃣ **ADM_MODULAR** (La Puerta de Entrada / Gateway)
**Tecnología:** Python + FastAPI
**Puerto:** 8000

**¿Qué hace?**
- Es el **portero del sistema**: verifica que quien hace la consulta tenga permiso (token de acceso)
- **Registra todo**: cuántas consultas hace cada usuario, cuántos tokens de IA consume
- **Enruta las peticiones**: decide a qué módulo enviar cada consulta
- **Control de costos**: lleva la cuenta de cuánto cuesta cada interacción

**Flujo:**
```
1. Sandbox envía consulta con token → ADM verifica token
2. Si es válido → Envía consulta al módulo correspondiente
3. Recibe respuesta → Registra consumo en base de datos
4. Devuelve respuesta al Sandbox
```

**Base de datos (SQLite):**
- Tabla de usuarios
- Tabla de tokens de acceso
- Tabla de logs (registro de uso)

---

### 3️⃣ **gm_general_chat** (El Cerebro / Agente Principal)
**Tecnología:** Python + LangChain + LlamaIndex
**Puerto:** 7005

**¿Qué hace?**
- Es el **motor de inteligencia artificial** que procesa las consultas
- Se conecta a modelos de lenguaje (OpenAI GPT-4, Azure)
- Tiene **memoria de conversación** (recuerda lo que se habló antes)
- Puede usar **herramientas médicas especializadas**:
  - 🔍 Búsqueda de medicamentos
  - 📊 Códigos ICD-10 (clasificación de enfermedades)
  - 🧬 Interacciones entre medicamentos
  - 📚 Búsqueda en bases de datos médicas

**Proceso:**
```
1. Recibe consulta del ADM
2. Inyecta datos del paciente en el prompt del sistema
3. Envía al Medical Auditor para pre-validación
4. Procesa con IA (GPT-4 o Azure)
5. Envía respuesta al Medical Auditor para validación final
6. Devuelve respuesta validada
```

**Características especiales:**
- **Prompts configurables** (diferentes modos: general, pediátrico, emergencias)
- **Detección de idioma** (español/inglés)
- **Contador de tokens** (para control de costos)
- **Trazabilidad completa** (guarda cada paso en Redis)

---

### 4️⃣ **gm_voice** (El Transcriptor Clínico) 🟡 En Desarrollo
**Tecnología:** Python + FastAPI + faster-whisper / Speechmatics + Redis
**Puerto:** 7003 (chat3)

**¿Qué hace?**
- Convierte la **consulta médica oral** en un documento clínico estructurado (formato SOAP) de forma progresiva
- El médico envía audio en fragmentos (chunks) cada 3-4 minutos mientras atiende al paciente
- El sistema transcribe en segundo plano y va construyendo el documento en pantalla en tiempo real
- Al terminar la consulta, devuelve un documento completo con extracción de datos + sugerencias validadas

**Dos tiers de transcripción:**

| Tier | Motor STT | Caso de uso | Costo |
|------|-----------|-------------|-------|
| **Classic** | `faster-whisper` (CPU local, int8) | Consulta ambulatoria, medicina general | Fijo (no por minuto) |
| **Professional** | Speechmatics Medical API | UCI, pre-quirúrgico, oncología | Por minuto, registrado para facturación |

**Documento clínico que genera:**
- **Extracción fiel**: motivo de consulta, enfermedad actual, signos vitales, antecedentes, medicación actual
- **Sugerencias IA**: diagnóstico sugerido, medicamentos sugeridos, exámenes sugeridos
- **Alertas**: validadas por el Medical Auditor (contraindicaciones, interacciones)

**Flujo:**
```
1. HIS abre sesión → session_id único
2. Cada 3-4 min → envía chunk de audio + tier
3. Servidor devuelve 202 inmediatamente (no hay espera)
4. En segundo plano: Whisper/Speechmatics transcribe → GPT-4o-mini actualiza documento
5. Médico hace polling /status/{session_id} → ve el documento construirse
6. Consulta termina → HIS envía POST /end → documento final consolidado
```

**Infraestructura de estado:**
- Redis (`redis-voice`) almacena el estado de cada sesión: transcripción acumulada, documento parcial, tokens consumidos
- TTL: 2 horas por sesión
- El `asyncio.Lock()` serializa las llamadas a Whisper en CPU para evitar concurrencia

---

### 5️⃣ **medical_auditor** (El Guardián de Seguridad)
**Tecnología:** Python + FastAPI + GPT-4o-mini
**Puerto:** 8001

**¿Qué hace?**
- Es el **juez de seguridad** que valida TODAS las respuestas antes de entregarlas al médico
- Verifica que la IA no diga cosas peligrosas o incorrectas
- Compara las respuestas con los datos del paciente (alergias, edad, etc.)

**Dos capas de validación:**

**A) Pre-Procesamiento (antes de enviar al LLM):**
- Detecta si la pregunta tiene sentido médico
- Identifica entidades médicas (medicamentos, síntomas, etc.)
- Rechaza preguntas incoherentes o peligrosas

**B) Validación de Seguridad (después de la respuesta):**
- Verifica que la respuesta no contradiga los datos del paciente
- Detecta alergias cruzadas
- Valida dosis de medicamentos
- Marca alertas si encuentra problemas

**Caché Semántico (Redis):**
- Si ya validó una pregunta similar, responde instantáneamente
- Ahorra tiempo y dinero (no llama a la IA dos veces)

**Ejemplo:**
```
Pregunta: "Dar amoxicilina a paciente"
Datos paciente: Alergia a penicilina
Auditor: ⚠️ ALERTA - Amoxicilina es una penicilina, contraindicado
```

---

## 🔄 Flujo Completo de una Consulta

```mermaid
Usuario (Sandbox) 
    ↓ [1. Consulta + Token]
ADM Gateway
    ↓ [2. Validación Token]
    ↓ [3. Envía a GM General Chat]
GM General Chat
    ↓ [4. Pre-Auditoría]
Medical Auditor (Pre-proceso)
    ↓ [5. OK → Continuar]
GM General Chat
    ↓ [6. Procesa con IA (GPT-4)]
    ↓ [7. Respuesta generada]
Medical Auditor (Validación)
    ↓ [8. Valida contra datos paciente]
    ↓ [9. OK o ALERTA]
GM General Chat
    ↓ [10. Respuesta final]
ADM Gateway
    ↓ [11. Registra consumo]
    ↓ [12. Devuelve respuesta]
Usuario (Sandbox)
```

---

## 🗄️ Servicios de Soporte

### **Redis** (Base de datos en memoria)
- Almacena sesiones de chat
- Guarda trazas de auditoría
- Caché semántico del Medical Auditor
- Memoria de conversaciones

### **Docker** (Contenedores)
- Cada módulo corre en su propio contenedor
- Facilita despliegue y escalabilidad
- Red interna `gomedisys-net` para comunicación entre servicios

---

## 📊 Datos que Maneja el Sistema

### **Entrada (Request):**
```json
{
  "message": "¿Qué antibiótico puedo usar?",
  "context": {
    "patient_age": 45,
    "patient_gender": "Masculino",
    "allergies": "Penicilina",
    "previous_diagnosis": "Hipertensión"
  },
  "prompt_mode": "medical_general",
  "tools": "drug_search"
}
```

### **Salida (Response):**
```json
{
  "status": "success",
  "data": {
    "response": "Para un paciente con alergia a penicilina...",
    "auditor_alert": false
  },
  "session_id": "chat_abc123",
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 200,
    "total_tokens": 350
  }
}
```

### **Traza de Auditoría:**
```json
[
  {"step": "INPUT_RECEIVED", "timestamp": "2026-02-03T18:00:00"},
  {"step": "SYSTEM_PROMPT_INJECTED", "data": "..."},
  {"step": "AUDITOR_PRE_PROCESS", "status": "OK"},
  {"step": "LLM_RAW_OUTPUT", "response": "..."},
  {"step": "AUDITOR_SAFETY_VALIDATION", "status": "OK"},
  {"step": "FINAL_RESPONSE_SERVED"}
]
```

---

## 🛠️ Herramientas Médicas Disponibles

1. **drug_search**: Búsqueda de medicamentos
2. **icd10**: Códigos de clasificación de enfermedades
3. **drug_interactions**: Interacciones entre medicamentos
4. **medical_guidelines**: Guías clínicas
5. **lab_values**: Valores de laboratorio

---

## 🔐 Seguridad y Control

### **Autenticación:**
- Tokens tipo `hcg_xxxxxxxxxxxxx`
- Validación en cada petición
- Asociados a usuarios con roles

### **Auditoría y Aprendizaje Continuo (RLHF):**
- **Traza Forense**: Cada consulta genera una traza completa guardada en `audit_log.jsonl`.
- **Detección de Anomalías**: El sistema identifica automáticamente bloqueos o alertas y los separa en `anomalies.jsonl` para revisión prioritaria.
- **Feedback Médico de Expertos**: Los médicos pueden validar respuestas y proponer correcciones globales a través de un endpoint dedicado.
- **Dataset de Entrenamiento**: Generación automática de `training_data.jsonl`, permitiendo que el sistema aprenda de los mejores médicos de la institución.
- Permite RLHF (Reinforcement Learning from Human Feedback) para especializar el modelo en protocolos locales.

### **Control de Costos:**
- Contador de tokens por usuario
- Registro de consumo por endpoint
- Logs de uso para facturación

---

## 📁 Estructura de Archivos

```
CHAT-GOMedisys/
├── CLINICAL_SANDBOX/          # Frontend (React)
│   ├── src/
│   │   ├── App.jsx           # Componente principal
│   │   └── index.css         # Estilos
│   └── Dockerfile
│
├── ADM_MODULAR/               # Gateway
│   ├── main.py               # API principal
│   ├── auth.py               # Autenticación
│   ├── database.py           # Conexión SQLite
│   └── models.py             # Modelos de datos
│
├── gm_general_chat/           # Agente IA
│   ├── main.py               # Motor principal
│   ├── providers.py          # Gestión de LLMs
│   ├── prompt_manager.py     # Gestión de prompts
│   ├── prompts.yml           # Configuración de prompts
│   └── mcp/medical_tools.py  # Herramientas médicas
│
├── medical_auditor/           # Validador
│   └── src/
│       ├── main.py           # API de auditoría
│       └── clinical_prompts.yml
│
└── docker-compose.yml         # Orquestación
```

---

## 🚀 Cómo Funciona en Producción

### **Inicio del Sistema:**
```bash
docker-compose up -d
```

Esto levanta:
- Clinical Sandbox (puerto 5173)
- ADM Gateway (puerto 8000)
- GM General Chat (puerto 7005)
- Medical Auditor (puerto 8001)
- Redis (puerto 6379)

### **Flujo de Trabajo:**
1. Médico abre `http://localhost:5173`
2. Ingresa token de acceso
3. Escribe consulta con datos del paciente
4. Sistema procesa y valida
5. Muestra respuesta + traza de auditoría

---

### 🔍 **Conectividad Externa (MCP)**
El sistema no solo depende del conocimiento del modelo de lenguaje, sino que utiliza el **Model Context Protocol (MCP)** para consultar fuentes externas certificadas:
- **Herramientas**: FDA, PubMed, ClinicalTrials, ICD-10.
- **Flujo**: El usuario hace una pregunta → La IA decide qué herramienta necesita → Realiza la consulta externa → Formatea el resultado con contexto médico.

### **Caso 1: Consulta Simple**
```
Pregunta: "¿Qué es la hipertensión?"
Respuesta: Explicación médica general
Auditor: ✅ OK (información general, sin riesgo)
```

### **Caso 2: Consulta con Contexto**
```
Pregunta: "¿Qué antibiótico puedo usar?"
Contexto: Paciente con alergia a penicilina
Respuesta: "Recomiendo azitromicina o ciprofloxacino..."
Auditor: ✅ OK (no hay contraindicaciones)
```

### **Caso 3: Alerta de Seguridad**
```
Pregunta: "¿Puedo dar aspirina?"
Contexto: Paciente con úlcera gástrica activa
Respuesta: "La aspirina puede ser útil para..."
Auditor: ⚠️ ALERTA - Contraindicado por úlcera gástrica
Respuesta final: [Respuesta original] + ⚠️ AUDITORÍA CLÍNICA: No administrar...
```

### **Caso 4: Rechazo de Pregunta**
```
Pregunta: "¿Cómo hacer una bomba?"
Auditor: 🚫 RECHAZADO - Pregunta no médica
Respuesta: "Lo siento, solo puedo responder consultas médicas"
```

---

## 📈 Métricas y Monitoreo

### **Endpoints de Salud:**
- `GET /health` - Estado de cada servicio
- `GET /admin/logs` - Últimas 10 consultas
- `GET /admin/tokens` - Tokens activos
- `GET /audit/trace/{session_id}` - Traza completa de una sesión

### **Datos Registrados:**
- Número de consultas por usuario
- Tokens consumidos (costo)
- Tiempo de respuesta
- Tasa de alertas del auditor
- Herramientas más usadas

---

## 🔧 Tecnologías Utilizadas

| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| Frontend | React + Vite | Interfaz de usuario |
| Backend | FastAPI (Python) | APIs REST |
| IA | OpenAI GPT-4, Azure | Procesamiento de lenguaje |
| Auditor | GPT-4o-mini | Validación de seguridad |
| Base de Datos | SQLite | Usuarios y logs |
| Caché | Redis | Sesiones y trazas |
| Orquestación | Docker Compose | Despliegue |
| Embeddings | Sentence Transformers | Búsqueda semántica |

---

## 🎓 Conceptos Clave para Explicar

### **1. Microservicios**
Cada parte del sistema es independiente. Si el auditor falla, el chat sigue funcionando (con modo degradado).

### **2. Trazabilidad**
Cada consulta deja un "rastro" completo de todo lo que pasó, útil para:
- Debugging
- Auditorías médicas
- Mejora continua (RLHF)

### **3. Inyección de Contexto**
Los datos del paciente se insertan en el "cerebro" de la IA para que dé respuestas personalizadas.

### **4. Validación Multi-Capa**
- Pre-validación (antes de procesar)
- Procesamiento (IA genera respuesta)
- Post-validación (verificación de seguridad)

### **5. Caché Semántico**
Si alguien pregunta "¿Qué es diabetes?" y luego otro pregunta "¿Qué significa diabetes?", el sistema reconoce que son similares y responde más rápido.

---

## 🚦 Estados del Sistema

### **Verde (OK):**
- Pregunta válida
- Respuesta segura
- Sin contraindicaciones

### **Amarillo (ALERT):**
- Respuesta generada pero con advertencias
- Se adjunta alerta del auditor
- Médico debe revisar con cuidado

### **Rojo (REJECTED):**
- Pregunta bloqueada
- Incoherencia clínica
- Pregunta no médica

---

## 📝 Resumen Ejecutivo

**GoMedisys es un sistema de IA médica con 4 capas:**

1. **Interfaz Web** (donde el médico interactúa)
2. **Gateway de Control** (verifica permisos y registra uso)
3. **Motor de IA** (procesa consultas con GPT-4)
4. **Auditor de Seguridad** (valida que todo sea seguro)

**Ventajas:**
- ✅ Seguro (doble validación)
- ✅ Trazable (registro completo)
- ✅ Personalizado (usa datos del paciente)
- ✅ Escalable (arquitectura modular)
- ✅ Controlado (tokens y costos)

**Tecnología:**
- Python + FastAPI (backend)
- React (frontend)
- OpenAI GPT-4 (IA)
- Redis (caché)
- Docker (despliegue)

---

## 🎯 Próximos Pasos (Roadmap)

- [x] Agente de Chat General (gm-general-chat :7001)
- [x] Agente de Resumen Clínico (gm-ch-summary :7006)
- [🟡] Agente de Voz — en desarrollo, rama `gm_voice_dev` (gm-voice :7003)
- [ ] Agente de Diagnóstico Diferencial (gm-diagnosis :7004)
- [ ] NER Médico compartido (gm-ner :7007) — rama `gm_ner_dev`
- [ ] Dashboard de Eficiencia y Facturación
- [ ] Exportación de reportes PDF
- [ ] Integración con HIS real (Hospital Information System)

---

**Versión del Sistema:** 2.0.0  
**Última Actualización:** Febrero 2026  
**Estado:** Producción (Beta)
