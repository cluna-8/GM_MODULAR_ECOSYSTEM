# 🎨 Diagrama Visual Simplificado - GoMedisys

## 📊 Vista de Arquitectura Completa

```
┌─────────────────────────────────────────────────────────────────┐
│                        👨‍⚕️ MÉDICO                                 │
│                    (Navegador Web)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  🖥️  CLINICAL SANDBOX (Frontend - React)                        │
│  Puerto: 5173                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Chat Box    │  │ Patient Data │  │  Inspector   │         │
│  │  (Consultas) │  │  (HIS Sim)   │  │  (Trazas)    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP Request + Token
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  🚪 ADM_MODULAR (Gateway - FastAPI)                             │
│  Puerto: 8000                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Auth Check   │  │  Log Usage   │  │   Router     │         │
│  │ (Tokens)     │  │  (SQLite)    │  │  (Modules)   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │ Validated Request
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  🤖 GM_GENERAL_CHAT (AI Engine - Python)                        │
│  Puerto: 7005                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. Recibe consulta + contexto paciente                  │  │
│  │  2. Inyecta datos HIS en system prompt                   │  │
│  │  3. Envía a Medical Auditor (pre-validación)             │  │
│  │  4. Procesa con LLM (GPT-4 / Azure)                      │  │
│  │  5. Envía respuesta a Medical Auditor (validación)       │  │
│  │  6. Devuelve respuesta final                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Herramientas: Drug Search, ICD-10, Interactions, Guidelines   │
└───────────┬─────────────────────────────────┬───────────────────┘
            │                                 │
            │ Pre-Check                       │ Safety Check
            ▼                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  🛡️  MEDICAL_AUDITOR (Safety Layer - GPT-4o-mini)              │
│  Puerto: 8001                                                   │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │  Pre-Procesamiento   │  │  Validación Final    │           │
│  │  - Coherencia        │  │  - Alergias          │           │
│  │  - Entidades         │  │  - Contraindicaciones│           │
│  │  - Riesgo inicial    │  │  - Dosis correctas   │           │
│  └──────────────────────┘  └──────────────────────┘           │
│                                                                 │
│  Caché Semántico (Redis) - Respuestas instantáneas             │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  💾 REDIS (Memoria y Caché)                                     │
│  Puerto: 6379                                                   │
│  - Sesiones de chat                                             │
│  - Trazas de auditoría                                          │
│  - Caché semántico                                              │
│  - Memoria de conversaciones                                    │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  🧠 RLHF & FEEDBACK LOOP (Mejora Continua)                      │
│  - anomalies.jsonl (Captura automática de riesgos)            │
│  - training_data.jsonl (Dataset para re-entrenamiento)        │
│  - Feedback Médico (Correcciones de expertos)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flujo de Datos Paso a Paso

```
PASO 1: Entrada del Usuario
┌──────────────────────────────────────────────────────────┐
│ Médico escribe: "¿Qué antibiótico para neumonía?"       │
│ Datos paciente: Edad: 45, Alergia: Penicilina           │
└──────────────────────────────────────────────────────────┘
                        ↓
PASO 2: Gateway (ADM)
┌──────────────────────────────────────────────────────────┐
│ ✓ Verifica token: hcg_abc123 → VÁLIDO                   │
│ ✓ Registra: Usuario "Dr. García" - Timestamp            │
└──────────────────────────────────────────────────────────┘
                        ↓
PASO 3: Agente IA - Preparación
┌──────────────────────────────────────────────────────────┐
│ System Prompt:                                           │
│ "Eres un asistente médico. Datos del paciente:          │
│  • Edad: 45 años                                         │
│  • Alergia: Penicilina                                   │
│  Considera estos datos en tu respuesta."                │
└──────────────────────────────────────────────────────────┘
                        ↓
PASO 4: Pre-Auditoría
┌──────────────────────────────────────────────────────────┐
│ Medical Auditor analiza:                                 │
│ ✓ Pregunta coherente: SÍ                                 │
│ ✓ Entidades detectadas: [neumonía, antibiótico]         │
│ ✓ Riesgo inicial: BAJO                                   │
│ → APROBADO para procesamiento                            │
└──────────────────────────────────────────────────────────┘
                        ↓
PASO 5: Procesamiento IA
┌──────────────────────────────────────────────────────────┐
│ GPT-4 genera respuesta:                                  │
│ "Para neumonía en paciente con alergia a penicilina,    │
│  recomiendo azitromicina 500mg/día por 5 días o         │
│  levofloxacino 750mg/día por 5 días..."                 │
└──────────────────────────────────────────────────────────┘
                        ↓
PASO 6: Validación de Seguridad
┌──────────────────────────────────────────────────────────┐
│ Medical Auditor valida contra datos paciente:           │
│ ✓ Azitromicina: NO es penicilina → SEGURO               │
│ ✓ Levofloxacino: Fluoroquinolona → SEGURO               │
│ ✓ Dosis apropiadas para edad                            │
│ → APROBADO sin alertas                                   │
└──────────────────────────────────────────────────────────┘
                        ↓
PASO 7: Registro y Respuesta
┌──────────────────────────────────────────────────────────┐
│ ADM registra:                                            │
│ - Tokens usados: 350 (150 prompt + 200 completion)      │
│ - Costo estimado: $0.0035                               │
│ - Tiempo: 2.3 segundos                                   │
└──────────────────────────────────────────────────────────┘
                        ↓
PASO 8: Visualización
┌──────────────────────────────────────────────────────────┐
│ Sandbox muestra:                                         │
│ [Respuesta formateada en Markdown]                       │
│                                                          │
│ Inspector muestra traza:                                 │
│ ✓ INPUT_RECEIVED                                         │
│ ✓ SYSTEM_PROMPT_INJECTED                                │
│ ✓ AUDITOR_PRE_PROCESS → OK                              │
│ ✓ LLM_RAW_OUTPUT                                         │
│ ✓ AUDITOR_SAFETY_VALIDATION → OK                        │
│ ✓ FINAL_RESPONSE_SERVED                                 │
└──────────────────────────────────────────────────────────┘
```

---

## ⚠️ Ejemplo de Alerta de Seguridad

```
ENTRADA:
┌──────────────────────────────────────────────────────────┐
│ Pregunta: "¿Puedo dar aspirina para el dolor?"          │
│ Paciente: Úlcera gástrica activa                        │
└──────────────────────────────────────────────────────────┘
                        ↓
PROCESAMIENTO NORMAL:
┌──────────────────────────────────────────────────────────┐
│ GPT-4 responde:                                          │
│ "La aspirina es efectiva para dolor leve a moderado.    │
│  Dosis recomendada: 500mg cada 6 horas..."              │
└──────────────────────────────────────────────────────────┘
                        ↓
VALIDACIÓN DE SEGURIDAD:
┌──────────────────────────────────────────────────────────┐
│ ⚠️ ALERTA DETECTADA                                      │
│ Razonamiento:                                            │
│ "La aspirina está CONTRAINDICADA en pacientes con       │
│  úlcera gástrica activa por riesgo de sangrado."        │
│                                                          │
│ Nivel de riesgo: ALTO                                    │
│ Estado: ALERT                                            │
└──────────────────────────────────────────────────────────┘
                        ↓
RESPUESTA FINAL:
┌──────────────────────────────────────────────────────────┐
│ [Respuesta original de GPT-4]                            │
│                                                          │
│ ⚠️ AUDITORÍA CLÍNICA:                                    │
│ CONTRAINDICACIÓN DETECTADA - La aspirina NO debe        │
│ administrarse a este paciente por úlcera gástrica       │
│ activa. Considere paracetamol como alternativa.         │
└──────────────────────────────────────────────────────────┘
```

---

## 🗄️ Estructura de Datos

### Token de Acceso
```json
{
  "token": "hcg_a1b2c3d4e5f6",
  "user_id": 1,
  "name": "Dr. García - Medicina Interna",
  "total_tokens_consumed": 15420,
  "created_at": "2026-01-15T10:00:00"
}
```

### Registro de Uso (Log)
```json
{
  "id": 1234,
  "token_id": 1,
  "endpoint": "chat1",
  "prompt_tokens": 150,
  "completion_tokens": 200,
  "total_tokens": 350,
  "timestamp": "2026-02-03T18:00:00"
}
```

### Traza de Auditoría
```json
{
  "session_id": "chat_abc123",
  "trace": [
    {
      "step": "INPUT_RECEIVED",
      "timestamp": "2026-02-03T18:00:00.123",
      "data": {
        "message": "¿Qué antibiótico...?",
        "context": {"patient_age": 45}
      }
    },
    {
      "step": "AUDITOR_PRE_PROCESS",
      "timestamp": "2026-02-03T18:00:00.456",
      "data": {
        "status": "OK",
        "risk_level": "LOW"
      }
    }
  ]
}
```

---

## 🎯 Componentes en Números

| Componente | Líneas de Código | Tecnología Principal | Función Principal |
|------------|------------------|---------------------|-------------------|
| Clinical Sandbox | ~500 | React + Vite | Interfaz de usuario |
| ADM Modular | ~200 | FastAPI + SQLite | Gateway y control |
| GM General Chat | ~1400 | LangChain + GPT-4 | Motor de IA |
| Medical Auditor | ~300 | FastAPI + GPT-4o-mini | Validación |
| **TOTAL** | **~2400** | Python + JavaScript | Sistema completo |

---

## 🔌 Puertos y Conexiones

```
Puerto 5173 → Clinical Sandbox (Frontend)
    ↓ HTTP
Puerto 8000 → ADM Gateway
    ↓ HTTP
Puerto 7005 → GM General Chat
    ↓ HTTP (bidireccional)
Puerto 8001 → Medical Auditor
    ↓ Redis Protocol
Puerto 6379 → Redis (Caché y Sesiones)
```

---

## 📦 Contenedores Docker

```
docker ps

CONTAINER ID   IMAGE                    PORT              STATUS
abc123         clinical-sandbox         5173:5173         Up
def456         adm-modular             8000:8000         Up
ghi789         gm-general-chat         7005:7005         Up
jkl012         medical-auditor         8001:8001         Up
mno345         redis:alpine            6379:6379         Up
```

---

## 🎓 Glosario de Términos

| Término | Significado |
|---------|-------------|
| **LLM** | Large Language Model (Modelo de Lenguaje Grande) - GPT-4 |
| **HIS** | Hospital Information System (Sistema de Información Hospitalaria) |
| **Token** | Unidad de texto que procesa la IA (~4 caracteres) |
| **Prompt** | Instrucción que se le da a la IA |
| **System Prompt** | Instrucción base que define el comportamiento de la IA |
| **Auditor** | Componente que valida seguridad de respuestas |
| **Gateway** | Punto de entrada único al sistema |
| **Trace** | Registro detallado de cada paso del procesamiento |
| **Session** | Conversación continua con memoria |
| **Embedding** | Representación numérica de texto para búsquedas |
| **Caché Semántico** | Almacén de respuestas similares para reutilizar |
| **RLHF** | Reinforcement Learning from Human Feedback |

---

## 🚀 Comandos Útiles

### Iniciar el sistema
```bash
cd /home/drexgen/Documents/CHAT-GOMedisys
docker-compose up -d
```

### Ver logs en tiempo real
```bash
docker-compose logs -f gm-general-chat
docker-compose logs -f medical-auditor
```

### Verificar estado
```bash
curl http://localhost:8000/health
curl http://localhost:7005/health
curl http://localhost:8001/health
```

### Detener el sistema
```bash
docker-compose down
```

---

## 📊 Métricas de Rendimiento

| Métrica | Valor Típico |
|---------|--------------|
| Tiempo de respuesta | 1.5 - 3 segundos |
| Tokens por consulta | 200 - 500 |
| Costo por consulta | $0.002 - $0.008 |
| Tasa de caché hit | 15-25% |
| Alertas del auditor | 5-10% de consultas |

---

**Este diagrama complementa el documento EXPLICACION_PROYECTO.md**
