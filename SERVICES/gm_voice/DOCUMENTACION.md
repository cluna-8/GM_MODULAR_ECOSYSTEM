# 🎤 GM_VOICE — Módulo de Transcripción Clínica Progresiva

Este módulo convierte una consulta médica oral en un documento clínico estructurado (SOAP) de forma progresiva, mientras el médico atiende al paciente.

## 💼 Resumen Ejecutivo

El módulo de voz elimina la carga administrativa del médico. Su función es:
- **Transcripción en tiempo real**: Procesa chunks de audio durante la consulta, sin que el médico espere.
- **Documento progresivo**: El médico ve el documento clínico construirse en pantalla mientras habla.
- **Dos tiers de calidad**: Classic (CPU local, costo fijo) o Professional (Speechmatics Medical, diarización nativa).
- **Sugerencias clínicas validadas**: Diagnóstico, medicamentos y exámenes sugeridos, revisados por el Medical Auditor.

---

## 🛠️ Especificación Técnica

- **Framework**: FastAPI (Python 3.11), procesamiento asíncrono con `BackgroundTasks`.
- **Tier Classic**: `faster-whisper` corriendo en CPU con cuantización int8 — sin costo por minuto, datos en el servidor.
- **Tier Professional**: Speechmatics Medical API — diarización médico/paciente, vocabulario clínico certificado.
- **Estado de sesión**: Redis (`redis-voice`) — acumula transcripción, documento parcial y tokens por sesión (TTL 2h).
- **Motor LLM**: GPT-4o-mini para actualización incremental del documento y consolidación final.
- **Seguridad**: Delegada al ADM Gateway. Este módulo solo acepta conexiones desde la red interna `gomedisys-net`.

---

## 📋 Flujo de una Consulta

```
1. HIS abre sesión → genera session_id
2. Cada 3-4 min → POST /chunk (audio + session_id + tier)
   → Respuesta inmediata: HTTP 202 (processing)
   → En background: transcripción → actualiza documento en Redis
3. HIS hace polling: GET /status/{session_id}
   → Devuelve documento parcial construido hasta ese momento
4. Consulta termina → POST /end (session_id)
   → Consolida documento final + sugerencias validadas por Auditor
```

---

## 🔌 Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| POST | `/chunk` | Recibe chunk de audio. Devuelve 202 inmediatamente. |
| POST | `/end` | Cierra sesión → documento final consolidado. |
| GET | `/status/{session_id}` | Estado actual del documento en construcción. |
| GET | `/health` | Health check del servicio. |

### Request `/chunk` — `multipart/form-data`
```
audio        = <archivo .mp3 / .wav>
session_id   = "voice_abc123"
chunk_number = 1
tier         = "classic" | "professional"
```

### Response `/status` y `/end`
```json
{
  "session_id": "voice_abc123",
  "status": "processing | complete",
  "chunks_processed": 2,
  "documento": {
    "motivo_consulta": "Dolor de cabeza fuerte en nuca hace 3 días",
    "enfermedad_actual": "Cefalea occipital con fotofobia y fiebre de 38.2",
    "signos_vitales": { "tension_arterial": "150/95" },
    "antecedentes": "Padre: derrame cerebral a los 65",
    "medicacion_actual": ["enalapril 5mg"],
    "diagnostico_sugerido": ["Meningitis bacteriana (descartar)"],
    "medicamentos_sugeridos": ["Paracetamol 1g cada 6h"],
    "examenes_sugeridos": ["Analítica urgente", "Punción lumbar"]
  },
  "alertas": [],
  "usage": {
    "input_tokens": 1240,
    "output_tokens": 380,
    "total_llm_tokens": 1620
  },
  "tier": "classic"
}
```

---

## 🏷️ Tiers de Servicio

### Classic
- **STT**: `faster-whisper` (CPU local, int8)
- **Modelo**: `small` por defecto, `medium` para mejor precisión médica
- **Ventaja**: Datos no salen del servidor. Sin costo por minuto de audio.
- **Limitación**: Sin diarización nativa (el LLM infiere hablantes por contexto clínico).

### Professional
- **STT**: Speechmatics Medical API
- **Ventaja**: Diarización médico/paciente. Vocabulario médico certificado en español.
- **Costo**: Por minuto de audio. Registrado en ADM Gateway con `tool_used = "voice_professional"`.

---

## 🔍 Cómo Probar

### Opción 1 — Test automático con TTS (desde Docker)
```bash
# Levantar el stack de voz
cd SERVICES/gm_voice
docker compose up -d

# Ejecutar test completo (genera audios, envía al ADM, verifica billing)
docker exec gm-voice python test_voice.py
```

### Opción 2 — Test con audio real desde host
```bash
# Enviar chunk directamente al servicio
curl -X POST http://localhost:7003/chunk \
  -F "audio=@/ruta/a/consulta.mp3" \
  -F "session_id=test_001" \
  -F "chunk_number=1" \
  -F "tier=classic"

# Polling del estado
curl http://localhost:7003/status/test_001

# Cerrar consulta
curl -X POST http://localhost:7003/end \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_001"}'
```

### Opción 3 — Test completo ADM → gm-voice
```bash
# Desde dentro del contenedor gm-voice
docker exec -e OPENAI_API_KEY=sk-... gm-voice \
  python test_adm_voice.py
```

**Resultados esperados:**
- `POST /chunk` devuelve HTTP 202 en menos de 1 segundo
- `GET /status` muestra documento parcial con campos extraídos
- `POST /end` devuelve documento completo con sugerencias
- ADM Gateway registra consumo en `api_requests` con `tool_used = "voice_classic"`

---

## 🗂️ Estructura de Archivos

```
SERVICES/gm_voice/
├── main.py           # FastAPI app — endpoints /chunk, /end, /status
├── transcriber.py    # Capa ASR: faster-whisper (Classic) y Speechmatics (Professional)
├── structurer.py     # GPT-4o-mini: actualización incremental y consolidación final del doc
├── auditor_client.py # Cliente fail-open hacia medical-auditor:8001
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env              # OPENAI_API_KEY, REDIS_URL, SPEECHMATICS_API_KEY, WHISPER_MODEL
├── test_voice.py     # Test directo al servicio (sin ADM)
└── test_adm_voice.py # Test E2E: ADM → gm-voice (incluye billing)
```

---

## ⚙️ Variables de Entorno

| Variable | Requerida | Valor por defecto | Descripción |
|----------|-----------|-------------------|-------------|
| `OPENAI_API_KEY` | Sí | — | Clave para GPT-4o-mini |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Modelo LLM para estructuración |
| `REDIS_URL` | No | `redis://redis-voice:6379/0` | Instancia Redis de sesiones |
| `SPEECHMATICS_API_KEY` | Solo Professional | — | Clave API Speechmatics |
| `WHISPER_MODEL` | No | `small` | Modelo faster-whisper (`small`, `medium`) |
| `PORT` | No | `7003` | Puerto del servicio |
