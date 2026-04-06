import os
import re
import json
from datetime import datetime
import uuid
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import openai

# Config logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config Env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI(
    title="Clinical History Summarizer",
    description="Microservice to parse and summarize raw electronic medical records",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    prompt_mode: Optional[str] = "medical"
    tools: Optional[str] = None
    session: Optional[str] = None
    language: Optional[str] = "auto"

SYSTEM_PROMPT = """You are an expert Clinical Data Extractor, Medical Auditor, and Summarizer. 
Your job is to read unstructured clinical notes (often multiple notes for the same patient) and output a STRICT JSON containing:
1. `resumen_clinico`: A single, well-balanced paragraph of approximately 1000 words summarizing the diagnosis, clinical evolution, treatments, medical history, exam results, and recommendations. Write this in clear, professional technical Spanish for other healthcare providers. Ignore any HTML formatting from the source.
2. `auditor_alerts`: An array of strings where you proactively flag any clinical discrepancies you find (e.g., age or gender mismatches across notes) OR critical severity alerts (e.g., severe hypotension, bradycardia, dangerous allergies). If none, return an empty array.
3. `medical_entities_extracted`: A JSON object extracting key entities: `{"diagnosticos": [], "tratamientos": [], "alergias": [], "signos_criticos": []}`.

You MUST reply ONLY with valid JSON. No markdown blocks, no additional text.

Example Output format:
{
  "resumen_clinico": "...",
  "auditor_alerts": ["..."],
  "medical_entities_extracted": {
    "diagnosticos": ["..."],
    "tratamientos": ["..."],
    "alergias": ["..."],
    "signos_criticos": ["..."]
  }
}
"""

def clean_clinical_text(raw_text: str) -> str:
    """
    Cleans up line breaks and invalid characters that break the parser.
    As derived from NotebookLM analysis of PromptA vs PromptB.
    """
    cleaned = raw_text.replace('\\r', ' ').replace('\\n', ' ')
    cleaned = cleaned.replace('\r', ' ').replace('\n', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = ''.join(char for char in cleaned if (char.isprintable() or char == ' '))
    return cleaned.strip()

@app.post("/chat")
async def summarize_clinical_history(request: ChatRequest):
    session_id = request.session or f"ch_{uuid.uuid4().hex[:12]}"
    
    try:
        cleaned_text = clean_clinical_text(request.message)
        logger.info(f"Session {session_id}: Text cleaned. Length={len(cleaned_text)}")
        
        response = await openai.ChatCompletion.acreate(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": cleaned_text}
            ],
            temperature=0.1
        )
        
        extracted_content = response['choices'][0]['message']['content']
        usage = response['usage']
        
        # Verify JSON 
        try:
            parsed_json = json.loads(extracted_content)
            # Dump back to string so it can be passed as the unified `response` string the frontend expects, 
            # but it will be a stringified JSON the frontend can parse.
            final_response = json.dumps(parsed_json, ensure_ascii=False)
        except json.JSONDecodeError:
            logger.warning(f"Session {session_id}: Failed to parse LLM JSON directly, returning as text.")
            final_response = extracted_content
            
        return {
            "status": "success",
            "data": {
                "response": final_response,
                "auditor_alert": False
            },
            "session_id": session_id,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }
        }
    
    except Exception as e:
        logger.error(f"Error in summarizing: {e}")
        return {
            "status": "error",
            "data": {"response": f"Error: {str(e)}"},
            "session_id": session_id,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "gm_ch_summary", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7006))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
