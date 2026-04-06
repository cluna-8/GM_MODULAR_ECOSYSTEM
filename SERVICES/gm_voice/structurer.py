import json
import logging
import os
from openai import AsyncOpenAI
from prompts import (
    SOAP_UPDATE_SYSTEM, SOAP_UPDATE_USER,
    SOAP_FINAL_SYSTEM, SOAP_FINAL_USER
)

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

EMPTY_DOCUMENT = {
    "motivo_consulta": None,
    "enfermedad_actual": None,
    "signos_vitales": {
        "tension_arterial": None,
        "frecuencia_cardiaca": None,
        "temperatura": None,
        "saturacion_oxigeno": None,
        "frecuencia_respiratoria": None,
        "peso": None,
        "talla": None
    },
    "antecedentes": None,
    "medicacion_actual": [],
    "diagnostico_sugerido": [],
    "medicamentos_sugeridos": [],
    "examenes_sugeridos": []
}


async def update_document(current_doc: dict, new_transcript: str, chunk_number: int) -> tuple[dict, dict]:
    """Update partial SOAP document with new transcript chunk.
    Returns (updated_doc, usage) where usage = {input_tokens, output_tokens, total_tokens}.
    """
    response = await client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SOAP_UPDATE_SYSTEM},
            {"role": "user", "content": SOAP_UPDATE_USER.format(
                documento=json.dumps(current_doc, ensure_ascii=False, indent=2),
                chunk_number=chunk_number,
                transcript=new_transcript
            )}
        ]
    )
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens
    }
    raw = response.choices[0].message.content
    try:
        return json.loads(raw), usage
    except json.JSONDecodeError:
        logger.error(f"LLM returned invalid JSON on update: {raw[:200]}")
        return current_doc, usage


async def consolidate_final(documento: dict, accumulated_transcript: str) -> tuple[dict, dict]:
    """Final pass: complete document + generate clinical suggestions.
    Returns (final_doc, usage).
    """
    response = await client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SOAP_FINAL_SYSTEM},
            {"role": "user", "content": SOAP_FINAL_USER.format(
                transcript=accumulated_transcript,
                documento=json.dumps(documento, ensure_ascii=False, indent=2)
            )}
        ]
    )
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens
    }
    raw = response.choices[0].message.content
    try:
        return json.loads(raw), usage
    except json.JSONDecodeError:
        logger.error(f"LLM returned invalid JSON on final consolidation: {raw[:200]}")
        return documento, usage
