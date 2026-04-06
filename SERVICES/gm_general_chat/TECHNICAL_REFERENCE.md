# Technical Reference Guide: gm_general_chat

## 1. System Overview
`gm_general_chat` is the primary interaction engine for the GoMedisys platform. It utilizes a **Hybrid Orchestration Architecture** that combines LlamaIndex for medical reasoning with a dedicated sub-service for clinical auditing.

## 2. Technical Stack
- **Engine**: Python 3.11+ / FastAPI.
- **Orchestration**: LlamaIndex (Advanced RAG and Tool-use frameworks).
- **Providers**: `ProviderManager` abstracts multiple backends (Azure OpenAI / OpenAI) with dynamic fallback.
- **Memory Tier**: Redis Stack (used for sliding-window conversation history and audit step tracking).
- **Communication**: Asynchronous HTTP (httpx/aiohttp) for microservice-to-microservice talk.

## 3. Storage & Persistence Strategy

### 3.1. Volatile Memory (Redis)
- **Session History**: Stores the last `N` messages to maintain clinical context without overloading LLM tokens.
- **Audit Traces**: Non-persistent hash maps (`audit_trace:{session_id}`) that track the internal flow of a request.
- **Prompt Cache**: Fast-access cache for system messages to avoid disk I/O.

### 3.2. Forensic Persistence (Filesystem)
- **Path**: `/logs/audit_log.jsonl`
- **Mechanism**: At the end of every successful interaction, the `HybridChatConfig` gathers the full Redis trace and appends it to this file in a single atomic operation.

## 4. Key Components Detail

### 4.1. ProviderManager (`providers.py`)
Implements an Abstract Base Class (`BaseProvider`) pattern. Supported types:
- **AzureProvider**: Configured via `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT_NAME`.
- **OpenAIProvider**: Uses GPT-4o-mini as default for high-speed clinical responses.

### 4.2. MedicalAuditorClient (`main.py`)
A specialized client that performs two critical HTTP calls per interaction:
1. `audit_pre_process`: Logic analysis of the user's intent.
2. `audit_validate_safety`: Post-analysis of the AI response against patient context (Age, Gender, Diagnosis).

### 4.3. PromptManager (`prompt_manager.py`)
A CRUD-enabled manager for medical instructions:
- **Source**: `prompts.yml`.
- **Sync**: Automatically replicates YAML changes to Redis for "Hot Reload" capability without restarting the container.
