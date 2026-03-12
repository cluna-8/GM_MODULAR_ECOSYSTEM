# Operational Integration Manual: medical_auditor

## 1. Internal API Endpoints

### 1.1. Preliminary Clinical Audit
**Endpoint**: `POST /audit/pre-process`
**Payload**:
```json
{
  "text": "What is the medical treatment for appendectomy?"
}
```
**Expected Response (REJECTED)**:
```json
{
  "status": "REJECTED",
  "verdict": "⚠️ INCONSISTENCY: Appendectomy is a surgical removal. It does not have a medical treatment; it is the treatment.",
  "entities": ["Appendectomy"]
}
```

### 1.2. Safety & HIS Context Validation
**Endpoint**: `POST /audit/validate-safety`
**Payload**:
```json
{
  "text": "The patient should take aspirin.",
  "context": {
    "edad": 80,
    "diagnostico": "Gastric Ulcer"
  }
}
```
**Expected Response (ALERT)**:
```json
{
  "status": "ALERT",
  "verdict": "Aspirin is contraindicated for patients with active gastric ulcers.",
  "metadata": {"risk_level": "HIGH"}
}
```

## 2. Term Standardization (Future Proofing)
**Endpoint**: `GET /terms/standardize?query=hipertension`
- Maps input strings to ICD-10 or SNOMED-CT codes. Currently returns placeholders (`CIE-10: I10`).

## 3. High Availability & Monitoring

### 3.1. Health Check
`GET /health`
Returns the status of the service and current model version.

**Example Response**:
```json
{
  "status": "healthy",
  "service": "medical-auditor",
  "engine": "GPT-4o-mini",
  "version": "1.2.0"
}
```

### 3.2. Performance Verification
- **Cache Hit**: Indicated by the `[CACHED]` prefix in the `verdict` field.
- **Latency**: Calls to the `/audit/trace` in the `gm_general_chat` system will show the split between Cache time (<50ms) and LLM time (>2s).

## 4. Operational Best Practices
- **Strict JSON**: The Auditor expects and returns strict JSON. Any malformed input will result in a `422 Unprocessable Entity`.
- **API Key Management**: Ensure `OPENAI_API_KEY` is set in the environment (via `.env` file or Docker secrets).
- **Rate Limits**: OpenAI API has rate limits. Monitor usage via OpenAI dashboard.
- **Cost Monitoring**: Track API costs (typically $0.15-0.60 per 1K audits depending on complexity).
- **Fallback Strategy**: If API fails, service returns safe fallback (`status: "OK"`, `verdict: "Audit failed (fallback safety enabled)"`).

## 5. Migration Notes
For details on the BioMistral → GPT-4o-mini migration, see `MIGRATION_GPT4o_MINI.md`.
