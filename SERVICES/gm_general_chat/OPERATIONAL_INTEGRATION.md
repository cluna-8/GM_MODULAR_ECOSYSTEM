# Operational Integration Manual: gm_general_chat

## 1. Interaction Schemas

### 1.1. Modern Request (Standard)
**Endpoint**: `POST /chat`
```json
{
  "message": "Clinical query here",
  "session": "user-uuid-456",
  "prompt_mode": "medical",
  "context": {
    "genero": "F",
    "edad": 79,
    "diagnostico": "DIABETES MELLITUS"
  }
}
```

### 1.2. Legacy Request (Backward Compatible)
Existing clients can send the old schema; the Gateway will auto-map fields:
```json
{
  "promptData": "Clinical query here",
  "sessionId": "user-uuid-456",
  "IAType": "medical"
}
```

## 2. Response Structure
All responses follow the `StandardResponse` model:
```json
{
  "status": "success",
  "data": {
    "response": "Clinical answer...",
    "tool_used": "pubmed" 
  },
  "usage": {
    "total_tokens": 150
  },
  "provider": "azure"
}
```

## 3. Advanced Monitoring (The Audit Log)

### 3.1. Retrieving a Real-Time Trace
If you need to debug a specific interaction BEFORE it persists:
`GET /audit/trace/{session_id}`

### 3.2. Forensic Log Interpretation
Located at: `/logs/audit_log.jsonl`
Each line contains a `full_trace` array. Stages to watch:
- `INPUT_RECEIVED`: What exactly reached the API.
- `AUDITOR_PRE_PROCESS`: The BioMistral preliminary verdict.
- `LLM_RAW_OUTPUT`: The un-validated AI response.
- `AUDITOR_SAFETY_VALIDATION`: The final security check.

## 4. Prompt Modes Reference
- `medical`: General clinical reasoning (Default).
- `emergency`: Direct, concise, focused on alarm signs.
- `pediatric`: Dosage-conscious, parental tone.
- `pharmacy`: Pharmacological interactions and contraindications.

## 5. Deployment Notes
- **Redis Requirement**: The service will not start without a valid Redis connection (used for tracing).
- **Auditor Dependency**: Requires `medical_auditor` to be online for pre/post validation steps.
