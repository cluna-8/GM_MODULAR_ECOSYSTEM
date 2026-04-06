# Technical Reference Guide: medical_auditor

## 1. System Overview
The `medical_auditor` is the "Clinical Intelligence" core of GoMedisys. It provides high-speed, medically-aware validation using a combination of Large Language Models (LLMs) and Vector Search.

## 2. Intelligence Core: GPT-4o-mini (Primary) + BioMistral (Offline)
### Primary Audit Engine: GPT-4o-mini
- **Model**: `gpt-4o-mini` (OpenAI API)
- **Deployment**: Managed cloud inference via OpenAI
- **Key Features**:
  - **Structured Output**: Guaranteed JSON via `response_format={"type": "json_object"}`
  - **Chain of Thought**: Explicit reasoning in `reasoning` field for clinical explainability
  - **Cross-Allergy Detection**: Superior semantic understanding (e.g., Penicillin ↔ Amoxicillin)
  - **Temperature**: 0.0 (deterministic audits for medical safety)
- **Prompt Engineering**: Managed through `clinical_prompts.yml`, enforcing strict JSON output formats for automated parsing.

### Secondary Engine: BioMistral (Offline/Privacy Tasks)
- **Model**: `BioMistral/BioMistral-7B-Instruct-v1` (commented out in code)
- **Future Use Cases**: Document summarization, entity extraction, GDPR-compliant offline processing
- **Deployment**: vLLM or TGI (when needed)

## 3. High-Performance Semantic Cache (The Speed Layer)
To ensure sub-100ms response times for common queries, the auditor implements a sophisticated **Semantic Cache**:
- **Vector Engine**: `RedisSearch` using the `HNSW` (Hierarchical Navigable Small World) algorithm.
- **Distance Metric**: `COSINE` distance (Threshold: 0.95 similarity).
- **Embeddings Model**: `all-MiniLM-L6-v2` (384 dimensions), selected for its excellent balance between clinical accuracy and inference speed.
- **Index Lifecycle**: Automatically initialized on startup (`idx:medical_cache`).

## 4. Software Implementation
- **Framework**: FastAPI (Asynchronous request handling).
- **Schema Validation**: Pydantic models for input (`AuditRequest`) and results (`AuditResponse`).
- **Configuration**: Environment-driven with `REDIS_URL` and `VLLM_MODEL` toggles.

## 5. Security & Isolation
- **Data Locality**: The service processes all clinical audits within the `gomedisys-net` internal Docker network.
- **Stateless Design**: All long-term "intelligence" (cached verdicts) is stored in the shared Redis instance, allowing horizontal scaling of the Auditor pods.
