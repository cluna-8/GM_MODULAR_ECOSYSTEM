# GoMedisys — Ecosistema de Microservicios Clínicos

> **Rama activa:** `gm_voice_dev` — Integración del módulo de voz con el ecosistema completo.

Sistema modular de asistencia clínica basado en microservicios. Cada módulo resuelve una necesidad específica del flujo médico y se comunica a través del **ADM Gateway** centralizado.

---

## Arquitectura

```
                          ┌─────────────────────────────────┐
  Cliente / HIS  ──────►  │   ADM Gateway  :8000            │
  (Bearer hcg_xxx)        │   JWT + token accounting        │
                          │   SQLite: healthcare_gateway.db │
                          └──────┬──────┬──────┬────────────┘
                                 │      │      │
                    ┌────────────┘      │      └─────────────┐
                    ▼                   ▼                     ▼
           ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
           │ General Chat │   │   Clinical   │   │   Voice Module   │
           │  :7005        │   │   Summary    │   │   :7003          │
           │  chat1        │   │   :7006      │   │   chat3  🟡      │
           └──────┬───────┘   │   chat2      │   └──────────────────┘
                  │           └──────────────┘
                  ▼
        ┌─────────────────┐
        │ Medical Auditor │
        │ Pipeline 5 pasos│
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  redis-general  │
        │  db=0  chat     │
        │  db=1  voice    │
        └─────────────────┘
```

---

## Servicios

| Servicio | Contenedor | Puerto | Estado |
|---|---|---|---|
| ADM Gateway | `healthcare-api-gateway` | `8000` | ✅ Activo |
| General Chat | `healthcare-chat-api` | `7005` | ✅ Activo |
| Clinical Summary | `gm-ch-summary` | `7006` | ✅ Activo |
| Voice Module | `gm-voice` | `7003` | 🟡 En desarrollo |
| Redis | `redis-general` | `6379` | ✅ Activo |

> El módulo de diagnóstico (`gm-diagnosis :7004`) está pendiente de implementación.

---

## Estructura del Repositorio

```
SERVICES/
├── docker-compose.yml          ← Compose maestro (levanta todo)
├── ADM_MODULAR/                ← Documentación del gateway
├── gm_general_chat/            ← Docs del agente de chat clínico
├── gm_ch_summary/              ← Código + Dockerfile del resumen clínico
├── gm_voice/                   ← Código + Dockerfile del módulo de voz
└── medical_auditor/            ← Documentación del auditor médico

docs/
├── obsidian/                   ← Vault Obsidian (documentación técnica)
├── ARCHITECTURE_DIAGRAM.md     ← Diagrama Mermaid del sistema
├── MANUAL_API_CLIENTE.md       ← Manual de integración para clientes
└── *.pdf                       ← Referencias técnicas
```

> La demo local (`SERVICES/demo/`) y los archivos de audio están excluidos del repo — corren con `python3 -m http.server 8080`.

---

## Levantar el ecosistema

**Prerequisito:** crear la red Docker externa una sola vez.

```bash
docker network create gomedisys-net
```

**Levantar todos los servicios:**

```bash
cd SERVICES/
docker compose up -d --build
```

**Verificar estado:**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Detener sin borrar datos:**

```bash
docker compose stop
```

**Borrar todo incluyendo volúmenes:**

```bash
docker compose down -v
```

---

## Autenticación

El gateway maneja dos niveles de auth:

| Tipo | Header | Uso |
|---|---|---|
| JWT admin | `Authorization: Bearer <jwt>` | Gestión: crear usuarios, tokens, ver logs |
| Token médico | `Authorization: Bearer hcg_xxx` | Operaciones clínicas: chat, resumen, voz |

**Obtener JWT admin:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

---

## Endpoints principales

### Chat clínico (`chat1`)
```
POST /medical/chat
Body: { "message": "...", "prompt_mode": "medical" }
```

### Resumen clínico (`chat2`)
```
POST /medical/summary
Body: { "message": "<nota clínica o texto libre>" }
```

### Voz — flujo de consulta (`chat3`)
```
POST /medical/voice/start              ← inicia sesión
POST /medical/voice/chunk              ← multipart/form-data: audio + session_id + tier + chunk_number
GET  /medical/voice/status/{session_id} ← documento parcial en construcción
POST /medical/voice/end                ← consolida y cierra
```

**Tiers de voz:**
- `classic` — faster-whisper local (CPU, sin costo por minuto)
- `professional` — Speechmatics Medical API (diarización nativa, requiere API key)

**Tamaños de chunk soportados:** 30 s · 1 min · 2 min · 3 min · 5 min

---

## Módulo de Voz — Documento SOAP de salida

```json
{
  "session_id": "v_abc123",
  "status": "processing | complete",
  "chunks_processed": 3,
  "documento": {
    "motivo_consulta": "...",
    "enfermedad_actual": "...",
    "signos_vitales": { "tension_arterial": "120/80" },
    "antecedentes": "...",
    "medicacion_actual": [],
    "diagnostico_sugerido": [],
    "medicamentos_sugeridos": [],
    "examenes_sugeridos": []
  },
  "alertas": [],
  "usage": { "input_tokens": 1240, "output_tokens": 380, "total_llm_tokens": 1620 },
  "tier": "classic"
}
```

> Las secciones de sugerencias (diagnóstico, medicamentos, exámenes) son apoyo clínico — siempre requieren validación del médico.

---

## Variables de entorno

Cada servicio espera un archivo `.env` en su carpeta (excluido del repo):

| Servicio | Variables clave |
|---|---|
| `gm_voice/` | `OPENAI_API_KEY`, `PORT=7003` |
| `gm_ch_summary/` | `OPENAI_API_KEY`, `PORT=7006` |
| `gm_general_chat/` | `OPENAI_API_KEY`, `REDIS_URL` |

---

## Rama `gm_voice_dev`

Esta rama integra el módulo de voz (`gm-voice`) al ecosistema completo:

- Proxy endpoints en el ADM Gateway (`/medical/voice/*`)
- Redis consolidado: un solo `redis-general` (db=0 chat/auditor, db=1 voice sessions)
- Compose maestro en `SERVICES/docker-compose.yml` que levanta todos los servicios
- Chunks configurables (30s a 5 min) con procesamiento progresivo del documento SOAP
- Demo local HTML con Web Audio API para dividir audios largos automáticamente

**Pendiente antes de merge a `main`:**
- Pruebas con audio real de consultas médicas en español
- Evaluar modelo `medium` vs `small` en terminología clínica

---

## Documentación

La documentación técnica completa está en `docs/obsidian/` (vault Obsidian):

| Nota | Contenido |
|---|---|
| `Index.md` | Mapa de contenido del ecosistema |
| `ADM_Gateway.md` | Gateway central, autenticación, billing |
| `Medical_Auditor.md` | Pipeline de seguridad clínica |
| `General_Chat.md` | Agente de chat clínico |
| `Clinical_Summary.md` | Motor de extracción de historias clínicas |
| `Voice_Module.md` | Transcripción clínica progresiva |
| `Infrastructure_Server.md` | Especificaciones del servidor de producción |
