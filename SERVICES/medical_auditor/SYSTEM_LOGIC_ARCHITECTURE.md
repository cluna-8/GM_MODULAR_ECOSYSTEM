# System Logic & Architecture Documentation: medical_auditor

## 1. Audit Logic Hierarchy
The Auditor functions through a tiered verification process designed to minimize latency without compromising clinical safety.

### Layer 1: The Vector Hit Layer (Semantic Memory)
1. **Embedding**: The input text is transformed into a 384-dimension vector.
2. **KNN Search**: A K-Nearest Neighbors search is performed in Redis.
3. **Threshold Gate**: 
   - If distance < 0.05 (Similarity > 95%): The cached `status` and `verdict` are returned immediately.
   - If no hit: The request proceeds to the LLM layer.

### Layer 2: Intent Audit (Pre-Process Logic)
This layer acts as the **"Sanity Filter"**.
- **Logic**: GPT-4o-mini analyzes the prompt to identify procedural vs. pathological entities.
- **Trap Detection**: It specifically looks for inconsistencies where a user treats a surgical outcome as a medical condition needing treatment (e.g., "medication for cholecystectomy").
- **Persistence**: Successful LLM verdicts are saved back to the Semantic Cache.

### Layer 3: Risk Audit (Safety Validation Logic)
This is the **"Post-Generation Judge"**.
- **Inputs**: The AI's generated response AND the patient's context (Gender, Age, Diagnosis, Allergies).
- **Clinical Reasoning (Chain of Thought)**: GPT-4o-mini checks for:
  - **Cross-Allergies**: Medications in the same family (e.g., Penicillin → Amoxicillin, both beta-lactams)
  - **Contraindications**: Medications that should not be taken given the current diagnosis.
  - **Age/Weight Risks**: Identifying advice that might be dangerous for pediatrics or geriatric patients.
  - **Hallucinations**: Filtering out medical advice that makes no sense in the HIS context.
- **Explainability**: The `reasoning` field provides step-by-step clinical logic for audit trails.

## 2. Asynchronous Pattern
The service uses Python's `async/await` throughout the lifecycle:
- **Async vLLM Calls**: Allows the service to handle hundreds of concurrent audits without blocking.
- **Async Redis IO**: Non-blocking vector searches and cache writes.

## 3. Knowledge Evolution
The Auditor's intelligence evolves through the `clinical_prompts.yml`. Updating this file allows for global logic changes (e.g., adding a new disease "trap" or a mandatory disclaimer) across the entire platform without changing the code.
