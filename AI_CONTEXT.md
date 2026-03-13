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

**Current branch:** `gm_ch_summary_dev` — adds the clinical summary module (Chat 2).
**Production branch:** `main` — only Chat 1 (general assistant) is currently in prod.
**Current version tag:** `v1.1.0` (proyecto global)
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
    ┌────┴────────────────────────┐
    ▼                             ▼
┌──────────────┐         ┌──────────────────┐
│ gm-general-  │ :7005   │ gm-ch-summary    │ :7006
│ chat (Chat1) │         │ (Chat2) — NEW    │
│ Medical Asst │         │ Clinical Summary │
└──────┬───────┘         └──────────────────┘
       │ audit calls
       ▼
┌──────────────────┐     ┌──────────────────┐
│ medical-auditor  │:8001│ redis-general    │:6379
│ Clinical Safety  │     │ Sessions + Cache │
│ Validator        │     │ (Redis Stack)    │
└──────────────────┘     └──────────────────┘
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

### 3.4 medical_auditor — Clinical Validator (Port 8001)
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

| Service | Key Pattern | Content | TTL |
|---------|-------------|---------|-----|
| gm_general_chat | `chat_{session_id}` | Full conversation history | 7 days |
| gm_general_chat | `prompts:{mode_name}` | PromptConfig JSON | none |
| gm_general_chat | `prompts:version` | Version string | none |
| gm_general_chat | `prompts:last_loaded` | ISO timestamp (hot reload) | none |
| medical_auditor | `cache:{hash(text)}` | Audit verdict + ADA-002 embedding | 1 hour |
| medical_auditor | (index) | `idx:medical_cache_ada002` HNSW | permanent |

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
| gm-general-chat | http://gm-general-chat:7005 | 7005 |
| gm-ch-summary | http://gm-ch-summary:7006 | 7006 |
| medical-auditor | http://medical-auditor:8001 | 8001 |
| redis-general | redis://redis-general:6379/0 | internal only |

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
