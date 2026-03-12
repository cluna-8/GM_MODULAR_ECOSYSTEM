# System Logic & Architecture Documentation: gm_general_chat

## 1. The Clinical Safety Pipeline
Every interaction goes through a 5-step deterministic pipeline to ensure medical accuracy and patient safety.

### Step 1: Input Normalization (The Bridge)
The system uses **Pydantic Validation Aliases** to support both modern and legacy clients.
- Logic: `promptData` manually maps to `message`; `sessionId` to `session`.
- Action: The `INPUT_RECEIVED` event is saved to the session trace.

### Step 2: Clinical Pre-Audit (The Gatekeeper)
Before any LLM token is generated, the system calls the `medical_auditor`.
- **Reasoning**: To detect "traps" (e.g., asking for treatment for a surgery).
- **Control Flow**: If the Auditor returns `REJECTED`, the system bypasses the LLM and returns the Auditor's clinical warning immediately.

### Step 3: LlamaIndex Orchestration (The Reasoning)
If cleared, the system initializes an `OpenAIAgent` or `ReActAgent` (LlamaIndex).
- **Instruction**: Pulls the specific medical prompt (Pediatric, Emergency, etc.) from the `PromptManager`.
- **Memory**: Merges the current message with the last 10 interactions retrieved from Redis.
- **Context**: Injects HIS data (Gender, Age, Diagnoses) into the system prompt.

### Step 4: Safety Cross-Check (The Validation)
The raw output from the LLM is sent back to the `medical_auditor`.
- **Purpose**: To check for contraindications (e.g., the AI recommending a drug that might conflict with the patient's existing diagnosis).
- **Trace**: This is recorded as `AUDITOR_SAFETY_VALIDATION`.

### Step 5: Final Serving & Forensic Log
The response is returned to the user, and the entire audit trace (including timing and raw data) is moved from Redis to the persistent `audit_log.jsonl`.

## 2. Dynamic Memory Logic
The system uses a **Sliding Window Memory** pattern:
- **Redis HSET**: Stores serialized `ConversationMemory` objects.
- **Auto-Pruning**: Truncates history automatically to keep context windows within LLM limits (e.g., keeping only the most relevant clinical history).

## 3. Language Intelligence
- **Detection**: The system uses a dedicated function to identify if the input is in Spanish or English.
- **Constraint**: It forces the LLM to reply in the detected language regardless of the medical prompt's base language.
