# AI_CONTEXT.md — GoMedisys Modular Ecosystem

Complete reference for AI agents. Read this file before touching any code.
**Do not commit this file.** It is listed in `.gitignore`.

**Target users of the system:** Healthcare professionals (doctors, nurses) using this
as a HIS (Hospital Information System) copilot. Not end patients. This distinction
matters for auditor thresholds — follow-up questions without explicit subject are
valid clinical workflow, not dangerous ambiguity.

---

## 1. What Is This Project

A modular AI medical assistant ecosystem built for Hospital Information Systems (HIS).
It exposes a gateway API that routes to specialized medical chat modules, validates
every interaction through an independent clinical auditor, and tracks all consumption
for billing purposes.

**Current branch:** `gm_voice_dev` — adds the voice module (Chat 3 / gm-voice :7003).
**Production branch:** `main` — Chat 1 (general assistant) + Chat 2 (clinical summary) in prod.
**Current version tag:** `v1.2.0-dev` (proyecto global)
**gm_general_chat internal version:** `2.0.0` (definida en el propio servicio)

---

## 2. System Architecture

```
Client (HIS / curl)
        │
        ▼
┌───────────────────┐   Port 8000
│  ADM_MODULAR      │   Gateway, Auth, Billing, Routing
│  (gateway)        │
└────────┬──────────┘
         │ httpx async proxy
    ┌────┴──────────────────────────────────┐
    ▼                    ▼                  ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ gm-general-  │  │ gm-ch-summary    │  │ gm-voice 🟡      │
│ chat :7001   │  │ :7006 (Chat2)    │  │ :7003 (Chat3)    │
│ Medical Asst │  │ Clinical Summary │  │ Voice → SOAP     │
└──────┬───────┘  └──────┬───────────┘  └──────┬───────────┘
       │                 │                      │
       └────────┬────────┘              ┌───────┴──────────┐
                ▼                       │  redis-voice      │
       ┌──────────────────┐             │  :6379 (sessions) │
       │ medical-auditor  │:8001        └──────────────────┘
       │ Clinical Safety  │     ┌──────────────────┐
       │ Validator        │     │ redis-general    │:6379
       └──────────────────┘     │ Sessions + Cache │
                                └──────────────────┘
```

**Docker network:** `gomedisys-net` (external — must exist before `docker-compose up`)
**Inter-service calls use container names** (e.g., `http://gm-general-chat:7005`)

---

## 3. Services

### 3.1 ADM_MODULAR — Gateway (Port 8000)
**Container:** `gateway`
**Code:** `SERVICES/ADM_MODULAR/`
**Purpose:** Single entry point. Validates Bearer tokens, proxies requests, logs billing.

**Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Lists active modules |
| POST | `/medical/chat` | Bearer | → Chat1 (general assistant) |
| POST | `/medical/summary` | Bearer | → Chat2 (clinical summary) |
| POST | `/v1/{module_id}/chat` | Bearer | Generic module routing |
| POST | `/admin/tokens` | No | Create API key |
| GET | `/admin/tokens` | No | List all tokens |
| GET | `/admin/usage/{token}` | No | Token consumption stats |
| GET | `/admin/logs` | No | Last 10 API calls |
| GET | `/admin/flagged-queries` | No | Auditor-flagged prompts |
| GET | `/admin/trace/{session_id}` | No | Full conversation trace (proxies to Chat1) |
| POST | `/audit/feedback` | Bearer | Expert feedback / RLHF (proxies to Chat1) |

**Key logic:**
- Validates `Authorization: Bearer hcg_xxx` via `HTTPBearer` → SQLite lookup → HTTP 401 if invalid
- `_validate_chat_payload()` enforces HTTP 422 if body has neither `promptData` nor `message`
- After each proxied call: captures `usage`, `auditor_alert`, `auditor_intercept` from response
- Writes `APILog` and increments `token.total_tokens_consumed`

**Database:** SQLite at `./modular_gateway.db`
Tables: `users` (id, username, role, is_active), `tokens` (id, token, user_id, name, total_tokens_consumed), `api_logs` (id, token_id, endpoint, tokens, auditor_alert, session_id, prompt_snippet, timestamp)
Can switch to Postgres via `DATABASE_URL` env var.

**After any gateway rebuild → re-seed:**
```bash
docker exec gateway python seed_internal.py
# Creates admin user + token hcg_maestro_123
```

---

### 3.2 gm_general_chat — Medical Assistant (Port 7005)
**Container:** `gm-general-chat`
**Code:** `SERVICES/gm_general_chat/`
**Purpose:** Main conversational medical assistant with tool access and persistent session memory.

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Main chat (accepts `message` or legacy `promptData`) |
| POST | `/tools/{tool_name}` | Direct tool call (fda, pubmed, icd10, clinical_trials) |
| GET | `/audit/trace/{session_id}` | Conversation audit trail |
| POST | `/audit/feedback` | Expert feedback storage |
| GET | `/health` | Service health |

**Request body:**
```json
{
  "message": "string",          // or "promptData" (legacy, both accepted)
  "session": "string",          // optional; omit to create new session
  "IAType": "medical",          // pass-through, ignored internally
  "tools": "fda|pubmed|icd10|clinical_trials|scraping",
  "prompt_mode": "medical|pediatric|emergency|pharmacy|general",
  "language": "auto|es|en"
}
```

**Response body:**
```json
{
  "status": "success|error",
  "data": { "response": "...", "auditor_intercept": false },
  "session_id": "chat_xxx",
  "provider": "openai|azure",
  "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 },
  "conversation_count": 1,
  "prompt_mode_used": "medical",
  "language_detected": "es"
}
```
When auditor blocks a query: `auditor_intercept: true`, `usage: null`, `conversation_count: null`.

**Prompt modes** (loaded from `prompts.yml`, cached in Redis):
- `medical` — full tool access, clinical professional discourse (default)
- `pediatric` — children, growth/development focus
- `emergency` — urgent triage, critical care protocols
- `pharmacy` — medication interactions, dosing
- `general` — health literacy, basic education

**Medical tools — estado verificado en producción:**
| Tool | Estado | Observación |
|------|--------|-------------|
| `fda` | ✅ Funciona | Requiere contexto clínico explícito o el auditor bloquea |
| `pubmed` | ✅ Funciona | Llama API real, devuelve abstracts |
| `icd10` | ⚠️ No dispara | LLM responde de memoria, no llama la API externa |
| `clinical_trials` | ⚠️ No dispara | LLM simula búsqueda, no llama ClinicalTrials.gov |
| `scraping` | ❓ No probado | Sin datos de producción |

**Session memory:**
- Backend: `RedisChatStore` (LlamaIndex), key: `chat_{session_id}`, TTL: 7 days
- 3000-token buffer; survives service restarts
- To continue a conversation: pass the same `session` value on every request

**LLM Providers:**
- Default: `openai` (gpt-3.5-turbo; override with `OPENAI_MODEL`)
- Optional: Azure OpenAI via `AZURE_OPENAI_*` env vars + `DEFAULT_PROVIDER=azure`

---

### 3.3 gm_ch_summary — Clinical Summary (Port 7006)
**Container:** `gm-ch-summary`
**Code:** `SERVICES/gm_ch_summary/`
**Purpose:** Parse raw messy clinical notes → structured JSON.
**Status:** NEW — only in `gm_ch_summary_dev`, not yet in production.

**Endpoint:** `POST /chat`
**Request uses `message` field, NOT `promptData`:**
```json
{ "message": "raw clinical text here", "prompt_mode": "medical" }
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "response": "{\"resumen_clinico\": \"...\", \"auditor_alerts\": [], \"medical_entities_extracted\": {\"diagnosticos\": [...], \"tratamientos\": [...], \"alergias\": [...], \"signos_criticos\": []}}",
    "auditor_alert": false
  },
  "session_id": "ch_{uuid}",
  "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
}
```

`data.response` is **stringified JSON** — must be parsed a second time by the client.
**Model:** `gpt-4o-mini` (better JSON fidelity).
**Pre-processing:** strips `\r\n`, collapses whitespace, removes non-printable chars.

---

### 3.4 gm_voice — Voice Module (Port 7003)
**Container:** `gm-voice`
**Code:** `SERVICES/gm_voice/`
**Status:** 🟡 In development — branch `gm_voice_dev`. Service built and tested locally.
**Purpose:** Chunked audio → progressive SOAP clinical document. Returns document while consultation is in progress.

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/chunk` | Receive audio chunk (multipart). Returns 202 immediately. |
| POST | `/end` | Close session → final consolidated SOAP document. |
| GET | `/status/{session_id}` | Poll document state during consultation. |
| GET | `/health` | Health check. |

**ADM gateway paths (proxied):**
| Method | Path | Auth |
|--------|------|------|
| POST | `/medical/voice/chunk` | Bearer |
| POST | `/medical/voice/end` | Bearer |
| GET | `/medical/voice/status/{session_id}` | Bearer |

**Request `/chunk`** — `multipart/form-data`:
```
audio        = <file .mp3 / .wav>
session_id   = "voice_abc123"
chunk_number = 1
tier         = "classic" | "professional"
```

**Response `/end` and `/status`:**
```json
{
  "session_id": "voice_abc123",
  "status": "processing | complete",
  "chunks_processed": 2,
  "documento": {
    "motivo_consulta": "...",
    "enfermedad_actual": "...",
    "signos_vitales": {},
    "antecedentes": "...",
    "medicacion_actual": [],
    "diagnostico_sugerido": [],
    "medicamentos_sugeridos": [],
    "examenes_sugeridos": []
  },
  "alertas": [],
  "usage": { "input_tokens": 0, "output_tokens": 0, "total_llm_tokens": 0 },
  "tier": "classic"
}
```

**Two tiers:**
- `classic`: faster-whisper CPU (int8, `small` model default, `medium` for better medical accuracy). No per-minute cost.
- `professional`: Speechmatics Medical API. Native speaker diarization. Per-minute billing tracked in ADM `api_requests` with `tool_used = "voice_professional"`.

**Key design decisions:**
- Session state is initialized in Redis **before** launching background task. This prevents 404 on immediate polling.
- `asyncio.Lock()` serializes Whisper CPU calls — prevents concurrent model access.
- `BackgroundTasks` returns 202 immediately; transcription runs async.
- Medical Auditor is called on `/end` to validate AI suggestions (fail-open — never blocks).
- Token counts accumulated across all LLM calls per session in Redis.

**Environment variables:**
```
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
REDIS_URL=redis://redis-voice:6379/0
SPEECHMATICS_API_KEY=...          # only needed for professional tier
WHISPER_MODEL=small                # or medium for better accuracy
PORT=7003
```

**Infrastructure:**
- Own Redis instance (`redis-voice`) isolated from `redis-general`
- `docker-compose.yml` in `SERVICES/gm_voice/`
- Connects to `gomedisys-net` (external network — must exist before up)

---

### 3.5 medical_auditor — Clinical Validator (Port 8001)
**Container:** `medical-auditor`
**Code:** `SERVICES/medical_auditor/src/`
**Purpose:** Independent clinical safety microservice. Not called by clients directly — called internally by Chat1.

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/audit/pre-process` | Validate user input before LLM |
| POST | `/audit/validate-safety` | Validate LLM output against patient context |
| GET | `/terms/standardize` | SNOMED/ICD-10 code translation |
| GET | `/health` | Service health |

**Pre-process request/response:**
```json
// Request
{ "text": "user query", "context": {} }

// Response
{
  "status": "OK|REJECTED",
  "verdict": "human-readable decision",
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "is_safe": true,
  "entities": ["entity1", "entity2"]
}
```

**Full audit pipeline:**
```
User input
    → Semantic cache lookup (Redis HNSW, cosine dist < 0.05 = cache hit)
        → Hit: return cached verdict (no LLM cost)
        → Miss: GPT-4o-mini (temp=0.0, JSON mode) → save to cache (TTL 1h)
    → REJECTED → block, return intercepted response
    → OK → continue to LLM

LLM output
    → audit/validate-safety
        → checks: contraindications, drug interactions, dosage errors
        → ALERT → ADM_MODULAR logs auditor_alert=True → appears in /admin/flagged-queries
        → OK → return normally
```

**Semantic cache:**
- Embeddings: OpenAI ADA-002 (1536-dim), Index: `idx:medical_cache_ada002` (HNSW)
- Threshold: cosine distance < 0.05 → cache hit
- TTL: 3600s per entry
- Benefit: common medical queries skip the LLM entirely → cost saving

**Fallback:** If GPT or Redis unavailable → defaults to `status=OK, is_safe=True` (fail-open, never blocks).

**Prompts config:** `SERVICES/medical_auditor/src/clinical_prompts.yml`
- `audit_pre_process`: detects incoherent/out-of-scope queries
- `audit_validate_safety`: checks contraindications, dosage, quality

---

## 4. Redis Keys Reference

| Service | Redis Instance | Key Pattern | Content | TTL |
|---------|---------------|-------------|---------|-----|
| gm_general_chat | `redis-general` | `chat_{session_id}` | Full conversation history | 7 days |
| gm_general_chat | `redis-general` | `prompts:{mode_name}` | PromptConfig JSON | none |
| gm_general_chat | `redis-general` | `prompts:version` | Version string | none |
| gm_general_chat | `redis-general` | `prompts:last_loaded` | ISO timestamp (hot reload) | none |
| medical_auditor | `redis-general` | `cache:{hash(text)}` | Audit verdict + ADA-002 embedding | 1 hour |
| medical_auditor | `redis-general` | (index) | `idx:medical_cache_ada002` HNSW | permanent |
| gm_voice | `redis-voice` | `voice:{session_id}` | Session state: transcript + documento + usage | 2 hours |

---

## 5. Authentication

```
1. Create token:  POST /admin/tokens  →  { "token": "hcg_abc123", "name": "..." }
2. Use token:     Authorization: Bearer hcg_abc123
3. Gateway validates: SQLite lookup → HTTP 401 if not found
4. Missing body:  HTTP 422 (enforced by _validate_chat_payload)
5. Every call:    APILog written, token.total_tokens_consumed incremented
```

Token format: `hcg_{uuid4().hex[:12]}`
JWT exists in `auth.py` but is **unused** — reserved for future admin panel.
`POST /admin/tokens` has **no auth** — restrict in production.

---

## 6. Environment Variables

### Shared: gm_general_chat + medical_auditor (same `.env` file)
```
OPENAI_API_KEY=sk-proj-...              # REQUIRED
OPENAI_MODEL=gpt-3.5-turbo             # or gpt-4o, gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
DEFAULT_PROVIDER=openai                # or "azure"
REDIS_URL=redis://redis-general:6379/0

# Azure (only if DEFAULT_PROVIDER=azure)
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### ADM_MODULAR
```
DATABASE_URL=sqlite:///./modular_gateway.db   # or postgresql://...
SECRET_KEY=una_clave_muy_secreta_para_produccion   # default en auth.py — CAMBIAR en prod
```

### gm_ch_summary
```
PORT=7006
OPENAI_MODEL=gpt-4o-mini
# OPENAI_API_KEY inherited from gm_general_chat .env
```

---

## 7. Docker

| Container | Internal URL | Host Port |
|-----------|-------------|-----------|
| gateway | http://gateway:8000 | 8000 |
| gm-general-chat | http://gm-general-chat:7001 | 7001 |
| gm-ch-summary | http://gm-ch-summary:7006 | 7006 |
| gm-voice | http://gm-voice:7003 | 7003 |
| medical-auditor | http://medical-auditor:8001 | 8001 |
| redis-general | redis://redis-general:6379/0 | internal only |
| redis-voice | redis://redis-voice:6379/0 | internal only |

```bash
# Start all
docker compose up -d

# Rebuild one service
docker compose build gateway && docker compose up -d gateway

# After gateway rebuild — always re-seed
docker exec gateway python seed_internal.py

# Logs
docker compose logs -f gm-general-chat
```

---

## 8. Test Scripts

| Script | Scope |
|--------|-------|
| `test_production.sh` | Full 8-phase suite: auth, chat, memory, tools, auditor, summary, billing, load |
| `test_flow.sh` | E2E: create token → chat → summary → trace |
| `test_summary.sh` | Isolated gm_ch_summary tests |
| `SERVICES/medical_auditor/test_auditor.py` | Auditor unit tests (cache, prompts, validation) |

---

## 9. Known Issues / Tech Debt

| # | Issue | Priority | Notes |
|---|-------|----------|-------|
| 1 | `conversation_count: null` on auditor intercepts | Low | Cosmetic only |
| 2 | `POST /admin/tokens` has no authentication | Pre-prod | Open to anyone |
| 3 | CORS allows all origins (`*`) | Pre-prod | Restrict before going live |
| 4 | `SECRET_KEY` has insecure default | Pre-prod | Must override via env |
| 5 | Summary `data.response` is stringified JSON | Low | Client must double-parse |

---

## 10. Complete Request Flow

```
POST /medical/chat  {"promptData": "¿Dosis de paracetamol?", "IAType": "medical"}
Authorization: Bearer hcg_maestro_123

1.  Gateway: validates token in SQLite ✓
2.  Gateway: _validate_chat_payload() → promptData present ✓
3.  Gateway: proxies to http://gm-general-chat:7005/chat
4.  Chat1:   detects language → "es"
5.  Chat1:   no session provided → generates "chat_abc123"
6.  Chat1:   calls medical-auditor /audit/pre-process
              → semantic cache miss → GPT-4o-mini → OK, LOW risk → cached (1h)
7.  Chat1:   loads MEDICAL prompt from Redis
8.  Chat1:   detects "paracetamol" → calls FDA tool → gets dosing data
9.  Chat1:   LLM generates response (system prompt + FDA data + question)
10. Chat1:   calls medical-auditor /audit/validate-safety → OK
11. Chat1:   saves turn to Redis (key: chat_abc123, TTL: 7 days)
12. Chat1:   returns response + usage stats
13. Gateway: writes APILog (tokens=537, session_id=chat_abc123, auditor_alert=False)
14. Gateway: increments token.total_tokens_consumed += 537
15. Client:  receives full response

Follow-up (same session):
16. Client sends: {"promptData": "¿Interacción con ibuprofeno?", "session": "chat_abc123"}
17. Chat1: loads Redis memory → context of previous turn available
18. conversation_count = 2
19. Auditor detects interaction risk → ALERT
20. Gateway logs auditor_alert=True
21. Appears in GET /admin/flagged-queries
22. Professional reviews via GET /admin/trace/chat_abc123
23. Submits correction via POST /audit/feedback
```
